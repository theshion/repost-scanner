# ===== Sirf ye lines badlo =====
COPY_ACCOUNT = "sydsweeney_admirer"    # jo account copy kar raha hai
ORIGINAL_ACCOUNT = "sydney_sweeney"    # asli account

DOWNLOAD = True               # False = Instagram ko koi request nahi, sirf phone ki photos match hongi
DOWNLOAD_ORIGINAL = False     # original pehle se phone mein hai to False hi rakho
WAIT_SECONDS = 12             # har nayi post ke beech ka wait (kam mat karo)
MAX_NEW_POSTS = 150           # ek run mein isse zyada nayi posts nahi lega; baaki agle din

# Login: pehli baar script khud 3 cookies poochegi (sessionid, csrftoken, ds_user_id).
# Wo phone mein save ho jati hain, is file mein kabhi nahi likhi jati.
# Naya login chahiye to Download folder se ".insta_session" file delete kar do.
# ===============================

import os, json, lzma, math, time, random
from PIL import Image, ImageOps

# Photos aur result kahan rahenge: phone par Download folder, warna script ke paas "data" folder.
PHONE_DIR = "/storage/emulated/0/Download"
BASE = os.environ.get("SCAN_DIR") or (
    PHONE_DIR if os.path.isdir(PHONE_DIR) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(BASE, exist_ok=True)
SESSION_FILE = os.path.join(BASE, ".insta_session")
CACHE_FILE = os.path.join(BASE, ".match_cache.json")
SURE_MATCH = 75        # isse upar = pakka match
MAYBE_MATCH = 70       # iske beech = khud check karo
STOP_AFTER_OLD = 5     # itni lagataar purani posts mile to download rok do (pinned posts ke liye margin)

N, K, S = 32, 8, 16
COS = [[math.cos(math.pi * (2 * x + 1) * u / (2 * N)) for x in range(N)] for u in range(K)]


# ---------------------------------------------------------------- download
def login():
    import instaloader
    L = instaloader.Instaloader(
        download_videos=False, download_comments=False, save_metadata=True,
        compress_json=False, post_metadata_txt_pattern="",
        max_connection_attempts=1,          # block aaye to baar-baar try na kare
        dirname_pattern=os.path.join(BASE, "{target}"))
    if os.path.exists(SESSION_FILE):
        L.load_session_from_file("saved", SESSION_FILE)
        print("Saved login mil gaya.")
    else:
        print("Pehli baar login: browser se Instagram ki 3 cookies paste karo.")
        cookies = {
            "sessionid": input("sessionid: ").strip(),
            "csrftoken": input("csrftoken: ").strip(),
            "ds_user_id": input("ds_user_id: ").strip(),
        }
        try:
            L.load_session("saved", cookies)
        except AttributeError:
            L.context.load_session("saved", cookies)
    username = L.test_login()
    if not username:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        raise RuntimeError("Login kaam nahi kar raha. Instagram app mein account kholo, "
                           "koi verification ho to poora karo, phir script dobara chalao "
                           "aur nayi cookies paste karo.")
    L.context.username = username
    L.save_session_to_file(SESSION_FILE)
    print(f"Login theek hai ({username}) aur phone mein save ho gaya.")
    return L


def download(L, username):
    import instaloader
    profile = instaloader.Profile.from_username(L.context, username)
    print(f"\n{username}: nayi posts check ho rahi hain (total {profile.mediacount})...")
    new, old = 0, 0
    for post in profile.get_posts():
        if L.download_post(post, target=username):
            new, old = new + 1, 0
            print(f"  {username}: nayi post {new}")
            if new >= MAX_NEW_POSTS:
                print(f"  Aaj ke liye {MAX_NEW_POSTS} ho gayi. Baaki ke liye kal dobara chalao.")
                break
            time.sleep(random.uniform(WAIT_SECONDS * 0.7, WAIT_SECONDS * 1.5))
        else:
            old += 1
            if old >= STOP_AFTER_OLD:
                break
    print(f"  {username}: {new} nayi posts aayi.")


def download_all():
    try:
        L = login()
        if DOWNLOAD_ORIGINAL:
            download(L, ORIGINAL_ACCOUNT)
        download(L, COPY_ACCOUNT)
    except Exception as e:
        print(f"\nDownload ruk gaya: {e}")
        print("Dobara turant mat chalao. Kam se kam 24 ghante ruko; "
              "jo download ho chuka hai wo agli baar skip ho jayega.")
        print("Abhi jitni photos phone mein hain unhi se match kar raha hoon.\n")


# ---------------------------------------------------------------- matching
def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("L")


def variants(img):
    """Copy wali photo ke alag roop: crop aur mirror, kyunki repost mein aksar ye badlav hote hain."""
    w, h = img.size
    s = min(w, h)
    out = [img, img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))]
    for m in (0.05, 0.1):
        out.append(img.crop((int(w * m), int(h * m), int(w * (1 - m)), int(h * (1 - m)))))
    out.append(ImageOps.mirror(img))
    return out


def phash(img):
    px = list(img.resize((N, N), Image.LANCZOS).tobytes())
    rows = [px[r * N:(r + 1) * N] for r in range(N)]
    tmp = [[sum(COS[u][x] * row[x] for x in range(N)) for u in range(K)] for row in rows]
    co = [[sum(COS[v][y] * tmp[y][u] for y in range(N)) for u in range(K)] for v in range(K)]
    flat = [co[v][u] for v in range(K) for u in range(K)][1:]
    med = sorted(flat)[len(flat) // 2]
    bits = 0
    for f in flat:
        bits = (bits << 1) | (f > med)
    return bits


def dhash(img):
    px = list(img.resize((S + 1, S), Image.LANCZOS).tobytes())
    bits = 0
    for r in range(S):
        for c in range(S):
            i = r * (S + 1) + c
            bits = (bits << 1) | (px[i] > px[i + 1])
    return bits


def ones(x):
    return bin(x).count("1")


def similarity(a, b):
    d = (ones(a[0] ^ b[0]) / 63 + ones(a[1] ^ b[1]) / (S * S)) / 2
    return 100 * (1 - d)


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_posts(username, with_variants, cache):
    """Har photo ka fingerprint. Ek baar nikala hua cache se aata hai, isliye agli baar bahut tez."""
    folder = os.path.join(BASE, username)
    if not os.path.isdir(folder):
        raise SystemExit(f"Folder nahi mila: {folder}\nPehle is account ko download karo.")
    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and "profile_pic" not in f)
    print(f"{username}: {len(files)} photos padh raha hoon...")
    posts, fresh = {}, 0
    for n, f in enumerate(files, 1):
        path = os.path.join(folder, f)
        key = f"{username}/{f}/{int(with_variants)}"
        stamp = int(os.path.getmtime(path))
        hit = cache.get(key)
        if hit and hit[0] == stamp:
            fps = [tuple(x) for x in hit[1]]
        else:
            try:
                img = load(path)
            except Exception:
                continue
            fps = [(phash(v), dhash(v)) for v in (variants(img) if with_variants else [img])]
            cache[key] = [stamp, fps]
            fresh += 1
        posts.setdefault(f.split("_UTC")[0] + "_UTC", []).extend(fps)
        if n % 50 == 0:
            print(f"  {n}/{len(files)}")
    print(f"  {fresh} nayi photos, {len(files) - fresh} cache se.")
    return folder, posts


def post_link(folder, base):
    for ext, opener in ((".json", open), (".json.xz", lzma.open)):
        p = os.path.join(folder, base + ext)
        if os.path.exists(p):
            try:
                with opener(p, "rt", encoding="utf-8") as f:
                    node = json.load(f).get("node", {})
                code = node.get("shortcode") or node.get("code")
                if code:
                    return f"https://www.instagram.com/p/{code}/"
            except Exception:
                pass
    return "(link nahi mila)"


def nice_date(base):
    return base.replace("_UTC", "").replace("_", " ")


def main():
    if not (COPY_ACCOUNT and ORIGINAL_ACCOUNT):
        raise SystemExit("Upar COPY_ACCOUNT aur ORIGINAL_ACCOUNT bharo.")
    if DOWNLOAD:
        download_all()

    cache = load_cache()
    copy_folder, copy_posts = read_posts(COPY_ACCOUNT, True, cache)
    orig_folder, orig_posts = read_posts(ORIGINAL_ACCOUNT, False, cache)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    print("\nMatch dhundh raha hoon...")

    sure, maybe, none = [], [], []
    for cbase, cfps in sorted(copy_posts.items()):
        best, best_o = 0, None
        for obase, ofps in orig_posts.items():
            s = max(similarity(a, b) for a in cfps for b in ofps)
            if s > best:
                best, best_o = s, obase
        row = (round(best, 1), cbase, best_o)
        if best >= SURE_MATCH:
            sure.append(row)
        elif best >= MAYBE_MATCH:
            maybe.append(row)
        else:
            none.append(cbase)

    def pair_lines(rows, label):
        out = []
        for n, (score, cbase, obase) in enumerate(sorted(rows, reverse=True), 1):
            out.append(f"{label} {n}  ({score}% same)")
            out.append(f"  Copy:     {post_link(copy_folder, cbase)}   [{nice_date(cbase)}]")
            out.append(f"  Original: {post_link(orig_folder, obase)}   [{nice_date(obase)}]\n")
        return out

    lines = [f"Copy: {len(copy_posts)} posts | Original: {len(orig_posts)} posts",
             f"Pakka match: {len(sure)} | Shayad: {len(maybe)} | Nahi mila: {len(none)}\n"]
    lines += pair_lines(sure, "MATCH")
    if maybe:
        lines.append("\n--- Shayad match, ek baar khud check kar lo ---\n")
        lines += pair_lines(maybe, "SHAYAD")
    if none:
        lines.append(f"\n--- In {len(none)} copy posts ka original nahi mila ---")
        for cbase in none:
            lines.append(f"  {post_link(copy_folder, cbase)}   [{nice_date(cbase)}]")

    text = "\n".join(lines)
    print("\n" + text)
    with open(os.path.join(BASE, "matches.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nResult yahan save hai: {os.path.join(BASE, 'matches.txt')}")


if __name__ == "__main__":
    main()
