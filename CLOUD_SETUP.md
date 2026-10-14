# Cloud Breviary automation

The daily Breviary build runs on GitHub Actions and does not depend on your Mac being awake or online. It fetches the required recordings from the public archive; it does not upload audio from your Mac. The workflow publishes the RSS XML to GitHub Pages first, verifies that copy, then syncs the same file to Flywheel and verifies the origin checksum over SSH.

The pipeline includes the 2026 special-day calendar, local archive resolution when available, public archive downloads when needed, St. Teresa regression coverage, Advent and Christmas handling, and Sunday second Vespers (`ep2`) handling. Local checks were completed for October 15, Advent 1, December 3, December 17, Christmas Day, and the Holy Family. The workflow also runs the resolver regression suite before every build.

## Destinations

- GitHub Pages: `https://fgi2016.github.io/kelex-breviary-feed/index.xml`
- Flywheel: `https://freelygiveninc.org/wp-content/uploads/breviary/kelex_breviary.xml`

The scheduled run is 23:07 Asia/Phnom_Penh (16:07 UTC) and builds tomorrow's feed. A manual `workflow_dispatch` run can target a particular date or, if left blank, also builds tomorrow's feed.

## Required GitHub setting

The dedicated Flywheel RSA private PEM is stored in this repository's Actions secrets as `FLYWHEEL_SSH_PRIVATE_KEY`. Its matching public key is registered with Flywheel. The workflow pins Flywheel's ED25519 SSH gateway fingerprint, uses that identity only for the RSS XML upload, and never prints the secret into logs.

## Flywheel cache note

Flywheel has previously served a cached copy of files under `/wp-content/uploads/` after the origin file had changed. The workflow now verifies the Flywheel origin file directly over SSH. The public CDN can still serve a cached feed URL until its cache expires; no cache setting or WordPress site setting is changed by this workflow. GitHub Pages is published and checksum-verified independently before the Flywheel step, so a Flywheel SSH outage does not prevent the GitHub Pages feed from updating.
