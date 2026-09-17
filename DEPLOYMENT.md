# AIVARO — Deployment Ready

## Render deployment

1. Push this project to a GitHub repository.
2. In Render, choose **New + → Blueprint** and select the repository.
3. Render will read `render.yaml`.
4. Add these environment variables in the Render dashboard if the app uses email:
   - `GMAIL_APP_PASSWORD` = your Gmail App Password
   - `GMAIL_ADDRESS` = the Gmail address used by the app (if your code expects it)
5. Deploy.

## Important security note

Do NOT commit real Gmail passwords, API keys, secret keys, or other credentials to GitHub.
Use Render Environment Variables instead.

## Start command

`gunicorn app:app`

This assumes the Flask application object is named `app` inside `app.py`.
