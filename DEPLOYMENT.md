# Day 14 — Deployment

## Railway

- Service agent Part 6 từ `06-lab-complete/`.
- Build Dockerfile multi-stage và health check `GET /health`.
- Redis chạy trong một dịch vụ riêng cùng project.
- **URL public:** [Agent trên Railway](https://k5-l3a-day14-nguyenlamhoang-2a202603448-deployme-production.up.railway.app/)

## Triển khai từ GitHub

1. Commit và push bản Part 6 đã kiểm tra lên repo GitHub cá nhân. Trong Railway, đăng nhập bằng GitHub và tạo project với hai service, **Agent** và **Redis**.
2. Kết nối service Agent với repo và branch vừa push. Trong **Agent → Settings**, đặt **Root Directory** là `/06-lab-complete` và **Config File** là `/06-lab-complete/railway.toml`.
3. Trong **Agent → Variables**, đặt `ENVIRONMENT=production` và một `AGENT_API_KEY` riêng. Đặt `REDIS_URL` bằng **Add Reference**, chọn biến `REDIS_URL` của service Redis trong cùng project. Nếu tên service là `Redis`, giá trị có dạng `${{Redis.REDIS_URL}}`.
4. Bấm **Deploy**. Khi service Agent chạy, vào **Settings → Networking → Public Networking → Generate Domain** trên Agent.

Để đưa riêng code và cấu hình Agent lên nhánh `main`, chạy từ gốc repo sau khi xác nhận `origin` là repo GitHub cá nhân:

```bash
git add 06-lab-complete/app 06-lab-complete/Dockerfile 06-lab-complete/.dockerignore 06-lab-complete/.env.example 06-lab-complete/docker-compose.yml 06-lab-complete/railway.toml
git diff --cached --stat
git commit -m "Complete Day 14 production agent"
git push origin main
```

## Cấu hình dịch vụ

Các biến dùng cho agent là `AGENT_API_KEY`, `REDIS_URL`, `ENVIRONMENT`, `RATE_LIMIT_PER_MINUTE`, `MONTHLY_BUDGET_USD` và `LOG_LEVEL`. Railway cấp `PORT`. Cấu hình API key và URL Redis trên Railway.

## Kiểm tra public URL

Chạy các lệnh sau trong Ubuntu. Terminal ẩn giá trị API key khi nhập.

```bash
BASE='https://k5-l3a-day14-nguyenlamhoang-2a202603448-deployme-production.up.railway.app'
read -rsp 'API key: ' AGENT_API_KEY
echo
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

| Kiểm tra trên Railway | Mã HTTP thực tế |
| --- | ---: |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu API key | 401 |
| `POST /ask` có API key hợp lệ | 200 |

## Minh chứng

- Agent và Redis đều Online. [Dashboard Railway](screenshots/dashboard.png)
- Deployment từ GitHub ở trạng thái Active. [Deployment thành công](screenshots/running.png)
- Terminal ghi nhận đủ bốn mã HTTP. [Kết quả kiểm tra](screenshots/test.png)
