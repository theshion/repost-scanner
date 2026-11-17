# Repost Scanner

Do Instagram accounts ki photos compare karke batata hai ki "copy" account ki kaun si post "original" account se uthai gayi hai. Chhoti ki hui, crop ki hui aur mirror ki hui photos bhi pakadta hai.

## Chalana

```bash
pip install -r requirements.txt
```

```bash
python repost_scanner.py
```

- Account names script ke upar ki lines mein hain.
- Pehli baar script Instagram ki 3 cookies poochti hai (`sessionid`, `csrftoken`, `ds_user_id`). Login save ho jata hai; cookies kabhi is file ya repo mein nahi likhi jati.
- Result `matches.txt` mein aata hai: phone par Download folder mein, warna `data/` folder mein.

## Background mein chalana (so jao, script chalti rahe)

Pehle ek baar seedha chala kar login save kar lo, phir:

```bash
nohup python repost_scanner.py > scan.log 2>&1 &
```

Progress dekhne ke liye:

```bash
tail -f scan.log
```

## Dhyan rahe

- Script jaan-boojh kar dheere chalti hai (har post ke beech ~12 second, ek run mein max 150 nayi posts) taaki Instagram account ko block na kare.
- Block aaye to turant dobara mat chalao; 24 ghante ruko.
