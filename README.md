# Roll the dice: a Streamlit app for Lesson 10

Students open the app on their phone, answer two predictions, roll a die 30 times
(the app rolls for them, or they type the results of a real die) and send.
You open the same address with `?teacher` at the end and see the class results live:

1. **Predictions**: what the class expected.
2. **Single rolls**: is the class die balanced?
3. **Averages**: single rolls, averages of 2, averages of 10; switch on the normal
   curves of the central limit theorem.
4. **Spread**: observed standard deviation against σ/√n.
5. **Data**: download the answers as CSV (save it as `data/class_dice.csv` in the course
   folder: `L10.qmd` and `dice_live.R` read it), add 20 example students for rehearsing,
   reset.

## Put it online (Streamlit Community Cloud, free, about 10 minutes)

1. Create a GitHub repository (it can be private) with the content of this folder:
   `app.py`, `requirements.txt`, `.streamlit/config.toml`.
2. Go to <https://share.streamlit.io>, sign in with GitHub, **Create app**,
   choose the repository, branch `main`, file `app.py`. Pick a short address,
   e.g. `asda-dice.streamlit.app`.
3. In the app settings, **Secrets**, write
   ```
   TEACHER_PASSWORD = "choose-a-password"
   ```
   (without it, the password is `dice`).
4. Students: `https://<your-app>.streamlit.app` (make a QR code for the slide).
   You: `https://<your-app>.streamlit.app/?teacher`.

**Before the lesson**: open the app a few minutes earlier. Free apps fall asleep after
some days without visits and take a minute to wake up. Use "Add 20 example students"
to rehearse, then **Reset** (the old answers are kept in a backup file on the server).

**Good to know**
- The answers are anonymous: no names, no e-mails.
- Answers are kept in memory and in a CSV file on the server. They survive a page
  reload, but not a redeploy or a long sleep of the app: download the CSV at the end
  of the lesson.
- With a few dozen students at once there is no problem.

## Run it on your laptop (to try it)

```
pip install -r requirements.txt
streamlit run app.py
```

Then open <http://localhost:8501> (students) and <http://localhost:8501/?teacher>.
Students can reach it only if they are on the same network as your laptop, so for
the lesson the online version is simpler.
