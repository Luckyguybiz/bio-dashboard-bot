# Shorts Command Center

## Overview

A lightweight command center for tracking YouTube Shorts performance and managing alerts.

## Environment Variables

See `.env.example` for required variables.

## Development

```bash
make fmt
make lint
make test
```

## Running

```bash
docker compose up -d
```

## Bot Commands

- `/addchannel <url|channel_id> [niche]`
- `/list`
- `/top [niche] [24h|7d]`
- `/gaps [niche]`
- `/ideas [niche] [N]`
- `/script "<topic>" [tone]`
- `/titles "<topic>"`
- `/postwindows`
- `/brief`

YouTube Data API quotas apply; use wisely.
