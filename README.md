# M5 hot water alerts

Checks https://reslife.lums.edu.pk/hot-water for hostel M5 every 10 minutes (6 am - 11 pm, Pakistan time)
and sends a phone notification through [ntfy](https://ntfy.sh):

- **"M5 checked - Left wing: ..., Right wing: ..."** when a warden logs a new check
- **"M5 water is HOT"** (high priority) when the hostel turns hot

"unknown" on the site means "not checked since the gas window opened", not cold, so it never triggers an alert.

## Setup

1. **Phone:** install the **ntfy** app (Play Store / App Store), tap **+**, and subscribe to your topic name
   (keep it secret, anyone who knows it can read/send to it).
2. **GitHub:** create a **public** repo and push this folder to it (public repos get free Actions minutes).
3. Repo **Settings > Secrets and variables > Actions > New repository secret**:
   name `NTFY_TOPIC`, value = your topic name.
4. Repo **Actions** tab > enable workflows > **Hot water check > Run workflow** to test.

The workflow commits `state.json` whenever something changes, so it remembers what it already told you.

## Run locally

```powershell
$env:NTFY_TOPIC = "your-topic"
python check_hot_water.py --test    # sends a test push
python check_hot_water.py --force   # real check, ignoring the time window
```

Change hostel with the `HOSTEL` env var (e.g. `HOSTEL: M3` in the workflow file).
