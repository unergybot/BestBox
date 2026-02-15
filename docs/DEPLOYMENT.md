# BestBox Customer Deployment

## 1) Bootstrap host

```bash
cd /home/unergy/BestBox
cp config/customer.yaml.example config/customer.yaml
cp .env.example .env
```

Fill `.env` and `config/customer.yaml` with customer-specific values.

## 2) Start core infrastructure

```bash
docker compose -f docker-compose.customer.yml up -d
```

## 3) Start AI services

```bash
source activate.sh
./start-all-services.sh
```

## 4) Seed customer knowledge base

```bash
mkdir -p data/customer_docs
# copy customer docs into data/customer_docs
scripts/seed-customer-kb.sh data/customer_docs
```

## 5) Sync Feishu docs (optional)

```bash
export FEISHU_APP_ID=...
export FEISHU_APP_SECRET=...
scripts/sync_feishu_docs.py
```

## 6) Health check

```bash
scripts/health-check.sh
```

## 7) Systemd install (optional)

```bash
sudo cp systemd/bestbox-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bestbox-api@${USER}
sudo systemctl enable bestbox-embeddings@${USER}
sudo systemctl enable bestbox-reranker@${USER}
sudo systemctl start bestbox-api@${USER} bestbox-embeddings@${USER} bestbox-reranker@${USER}
```

## Notes

- Enable strict tool authorization by setting `STRICT_TOOL_AUTH=true`.
- OpenAPI dynamic tools are enabled via `OPENAPI_SPEC_URL` and `OPENAPI_TOOL_ALLOWLIST`.
- OA integrations require `OA_WEBHOOK_URL`.
- IT Ops integrations require `PROMETHEUS_URL` (and optionally `LOKI_URL`).
