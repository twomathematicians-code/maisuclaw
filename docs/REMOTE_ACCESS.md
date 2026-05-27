# Remote Access — Use maisuclaw from Anywhere

## Option 1: Cloudflare Tunnel (Recommended, Free)

The easiest way to access maisuclaw from your phone, another city, or anywhere.

### One-time setup

1. **Download cloudflared** for Windows:
   - Go to https://github.com/cloudflare/cloudflared/releases
   - Download `cloudflared-windows-amd64.msi`
   - Install it

2. **Create a Cloudflare account** (free):
   - Go to https://dash.cloudflare.com/sign-up

3. **Run the tunnel**:
   ```cmd
   cloudflared tunnel --url http://localhost:8000
   ```
   This will output a URL like:
   ```
   https://random-name.trycloudflare.com
   ```

4. **Open that URL on any device** — phone, tablet, another computer.

### Make it permanent (optional)

Edit `scripts/cloudflare_tunnel.bat` with your tunnel name, or just use the quick tunnel above.

### Auto-start with maisuclaw

Add `cloudflared tunnel --url http://localhost:8000` to `setup_run.bat` before the uvicorn command. Or run it in a separate terminal.

---

## Option 2: Tailscale (VPN Mesh)

Good if you want a private connection without a public URL.

### Setup

1. Install Tailscale on your ThinkPad: https://tailscale.com/download
2. Install Tailscale on your phone
3. Log in to both with the same account
4. Find your ThinkPad's Tailscale IP (looks like `100.x.x.x`)
5. Open `http://100.x.x.x:8000` on your phone

### Advantages
- No public URL needed
- End-to-end encrypted
- Works even without internet (local network)

---

## Option 3: GitHub Pages (Static Frontend)

Host the web UI on GitHub Pages for a nice URL like `username.github.io/maisuclaw`.

### Setup

1. In your maisuclaw repo, create a `gh-pages` branch:
   ```cmd
   git checkout -b gh-pages
   git rm -r .
   cp -r static/* .
   git add .
   git commit -m "deploy ui to github pages"
   git push origin gh-pages
   ```

2. On GitHub, go to Settings → Pages → Source: `gh-pages` branch

3. Edit `static/app.js` — change the fetch URLs from `/chat` to your tunnel URL:
   ```js
   const API_BASE = "https://your-name.trycloudflare.com";
   // Then use: fetch(`${API_BASE}/chat`, ...)
   ```

4. Your UI is now at `https://username.github.io/maisuclaw`

### Note
The GitHub Pages site is just the frontend. The actual AI processing still happens on your ThinkPad via the Cloudflare Tunnel.

---

## Option 4: Render.com (Cloud Backend)

Host the FastAPI backend on Render.com's free tier.

### Limitations
- **Free tier does NOT run Ollama** — no local LLMs
- You would need to use cloud LLM APIs (OpenAI, Groq) as fallback
- Best used as a relay/proxy to your home machine

### Setup (if you want to try)

1. Create `render.yaml` in your repo:
   ```yaml
   services:
     - type: web
       name: maisuclaw
       runtime: python
       buildCommand: pip install -r requirements.txt
       startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
       envVars:
         - key: PYTHON_VERSION
           value: "3.11.0"
   ```

2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Render will deploy it

### Better approach: Render as proxy

Use Render to host a thin proxy that forwards requests to your home machine's Cloudflare Tunnel. This gives you a stable URL.

---

## Security Notes

- **Cloudflare Quick Tunnel** URLs are random and hard to guess, but publicly accessible
- **Tailscale** is the most secure option (private mesh VPN)
- **Never expose your Ollama port (11434) directly** — only the maisuclaw port (8000)
- **GitHub backup** uses a personal access token — keep it secret
- For production use, add authentication (basic auth, API keys, etc.)

## Quick Recommendation

| Need | Solution |
|------|----------|
| Access from phone at home | Just use `http://laptop-ip:8000` |
| Access from anywhere | Cloudflare Tunnel (easiest) |
| Private, no public URL | Tailscale |
| Nice URL for sharing | GitHub Pages + Cloudflare Tunnel |
| Cloud hosting | Render.com (limited, no Ollama) |
