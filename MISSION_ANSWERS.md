# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Phát hiện anti-patterns

Các dòng dưới đây thuộc [bản develop](01-localhost-vs-production/develop/app.py).

1. **Thông tin xác thực nằm trong mã nguồn (dòng 17–18).** Nếu dùng thông tin xác thực thật, người có quyền đọc repository hoặc lịch sử Git có thể lấy được chúng.
2. **Log bằng `print()` và in cả API key (dòng 33–38).** Người có quyền xem log có thể đọc được key thật. Các dòng log cũng thiếu trường có cấu trúc để lọc theo mức độ.
3. **Thiếu endpoint `GET /health` (dòng 42–43).** Nền tảng triển khai không thể dùng endpoint này để kiểm tra agent có đang phản hồi hay không.
4. **Server chỉ lắng nghe trên `localhost` (dòng 51).** Khi chạy trong container, reverse proxy hoặc client ở ngoài container không truy cập được agent qua interface mạng của container.
5. **Cổng `8000` được ghi cố định (dòng 52).** Nếu nền tảng cấp cổng khác qua biến `PORT`, server vẫn lắng nghe ở cổng 8000 và lưu lượng có thể không tới được app.
6. **Tự động nạp lại mã nguồn luôn bật (dòng 53).** Tiến trình theo dõi file làm tăng chi phí vận hành và có thể khởi động lại server khi file thay đổi.

### Exercise 1.2 — Chạy bản develop

```bash
curl -i -X POST 'http://localhost:8000/ask?question=Hello'
```

Kết quả từ terminal: `HTTP/1.1 200 OK`.

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Khi gọi `GET /health` trên cùng bản develop, terminal trả `HTTP/1.1 404 Not Found` và `{"detail":"Not Found"}`.

### Exercise 1.3 — So sánh với bản production

```bash
curl -i http://localhost:8000/health
```

Kết quả từ terminal khi chạy bản production: `HTTP/1.1 200 OK`.

```json
{"status":"ok","uptime_seconds":546.0,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T09:13:25.671500+00:00"}
```

Trường `environment` là `development` vì lần chạy này dùng giá trị mặc định của `ENVIRONMENT` trong `production/config.py:24`.

| Tính năng | Develop | Production | Vì sao quan trọng? |
| --- | --- | --- | --- |
| Cấu hình | Cổng 8000 ghi cố định ở `develop/app.py:52`. | Đọc `PORT` từ biến môi trường ở `production/config.py:18` và truyền vào Uvicorn ở `production/app.py:197`. | Có thể dùng cùng mã nguồn ở local và cloud với cấu hình phù hợp từng môi trường. |
| Health check | `GET /health` trả 404. | `production/app.py:135` khai báo `GET /health`. Khi chạy thử, endpoint trả 200 và `status: ok`. | Hệ thống giám sát có thể gọi một endpoint riêng để kiểm tra tiến trình có phản hồi. |
| Logging | Dùng `print()` và in cả API key ở `develop/app.py:33–38`. | Dùng module `logging` với mẫu log kiểu JSON, có thời gian, mức độ và thông điệp ở `production/app.py:28–30`. | Dễ lọc và tìm log khi điều tra lỗi. Tránh ghi thông tin xác thực giúp giảm nguy cơ lộ qua log. |
| Shutdown | Không có bước dọn dẹp riêng của ứng dụng. | Dùng `lifespan` của FastAPI để chạy bước shutdown sau `yield`, chuyển trạng thái readiness và ghi log. Xem `production/app.py:40–67`. | Khi dừng dịch vụ, ứng dụng có chỗ để đóng kết nối và giải phóng tài nguyên. Graceful shutdown cho phép request đang xử lý có cơ hội hoàn tất. |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

1. **Base image** là `python:3.11`, cung cấp Python 3.11 để cài thư viện và chạy ứng dụng.
2. **Thư mục làm việc** là `/app`. Các lệnh tiếp theo và những đường dẫn tương đối trong container dùng thư mục này.
3. **Copy `requirements.txt` trước mã nguồn** để Docker có thể dùng lại layer cài thư viện khi chỉ sửa `app.py`. Nếu `requirements.txt` thay đổi, Docker sẽ chạy lại bước cài thư viện.
4. **`ENTRYPOINT` và `CMD`** có vai trò khác nhau. Khi Dockerfile khai báo cả hai ở dạng exec, `ENTRYPOINT` là chương trình được chạy và `CMD` cung cấp đối số mặc định. Đối số đặt sau tên image trong `docker run` thay thế `CMD`. Dockerfile của bài đặt `CMD ["python", "app.py"]` làm lệnh khởi động mặc định.

### Exercise 2.2 — Build và chạy container develop

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run --rm -d --name day14-cp2-dev -p 8000:8000 my-agent:develop
curl -i http://localhost:8000/health
curl -i -X POST 'http://localhost:8000/ask?question=What%20is%20Docker%3F'
```

| Request | Mã HTTP | Phản hồi |
| --- | --- | --- |
| `GET /health` | `200 OK` | `{"status":"ok","uptime_seconds":26.0,"container":true}` |
| `POST /ask?question=What%20is%20Docker%3F` | `200 OK` | `{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}` |

### Exercise 2.3 — Multi-stage build

Stage `builder` dùng `python:3.11-slim`, cài công cụ build và các thư viện Python. Stage `runtime` bắt đầu từ một image `python:3.11-slim` riêng, copy thư viện đã cài ở builder và mã ứng dụng, rồi chạy dưới user `appuser`. Image cuối nhẹ hơn vì dùng base slim và bỏ các công cụ chỉ phục vụ build.

Kết quả đo bằng `docker image ls my-agent`:

| Image | Disk usage | Content size |
| --- | ---: | ---: |
| `my-agent:develop` | 1,67 GB | 426 MB |
| `my-agent:advanced` | 240 MB | 57,4 MB |

Theo cột `DISK USAGE`, quy đổi 1,67 GB thành khoảng 1.670 MB. Bản advanced giảm khoảng **85,6%** dung lượng so với develop, tính bằng `(1670 - 240) / 1670 × 100`.

### Exercise 2.4 — Docker Compose và Nginx

```text
Client → localhost:80 → Nginx → agent:8000
                                  ├─ Redis (redis:6379)
                                  └─ Qdrant (qdrant:6333)
```

Nginx nhận HTTP từ máy host và chuyển request vào agent qua mạng nội bộ của Compose. Hai nhánh Redis và Qdrant thể hiện cấu hình phụ thuộc trong Compose. Agent chờ hai service này vượt qua health check khi khởi động. Các request mẫu ở đây gọi agent dùng mock LLM.

```bash
curl -i http://localhost/health
curl -i -X POST http://localhost/ask -H 'Content-Type: application/json' -d '{"question":"Explain microservices"}'
```

| Request | Mã HTTP | Header | Phản hồi |
| --- | --- | --- | --- |
| `GET /health` | `200 OK` | `Server: nginx` | `{"status":"ok","uptime_seconds":64.0,"version":"2.0.0","timestamp":"2026-11-25T09:31:38.251356"}` |
| `POST /ask` | `200 OK` | `Server: nginx` | `{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}` |

## Part 3 — Cloud Deployment

### Railway và Render

Agent Part 6 dùng `06-lab-complete/railway.toml` với builder `DOCKERFILE` và probe `/health`. Với Railway, Redis là một dịch vụ riêng trong cùng project. Agent nhận `REDIS_URL` và `AGENT_API_KEY` qua biến môi trường của dịch vụ.

Render dùng Blueprint YAML để khai báo service, Docker runtime, health check và các biến môi trường. Secret có thể khai báo bằng `sync: false` hoặc `generateValue: true`. Một Blueprint có thể khai báo Redis và tham chiếu thông tin kết nối của nó thay cho cấu hình riêng trên từng dịch vụ.

Kết quả triển khai Railway và kiểm tra URL public sẽ được ghi trong `DEPLOYMENT.md`.

### Exercise 3.3 — Cloud Run

1. Cloud Build cài dependencies và chạy `pytest`.
2. Sau test, pipeline build Docker image, gắn tag theo commit SHA và tag `latest`, rồi push cả hai lên registry.
3. Pipeline dùng `gcloud run deploy` để triển khai image theo SHA ở `asia-southeast1` và cấp secrets từ Secret Manager.
4. `service.yaml` mô tả cấu hình dịch vụ, gồm số instance, concurrency, tài nguyên và các probe `/health`, `/ready`.

## Part 4 — API Security

### Exercise 4.1 — API key

`04-api-gateway/develop/app.py` lấy giá trị cấu hình từ `AGENT_API_KEY` và đọc header `X-API-Key` trong `verify_api_key` (dòng 35–52). Theo code, thiếu key trả `401`, còn key sai trả `403`. Để đổi key, cập nhật biến môi trường của dịch vụ, khởi động lại ứng dụng và cập nhật key ở các client.

Kết quả thực tế khi dùng đúng key demo:

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Kết quả thực tế khi gọi `POST /ask` với body JSON hợp lệ và bỏ header `X-API-Key`:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

### Exercise 4.2 — JWT

Client đăng nhập qua `POST /auth/token` để nhận JWT đã ký. Khi gọi `POST /ask`, client gửi JWT trong header `Authorization: Bearer <token>`. Server kiểm tra chữ ký và hạn sử dụng rồi lấy thông tin user và role từ token.

Tài khoản demo `student` lấy token thành công và dùng token gọi `/ask` với câu hỏi `Explain JWT`. Kết quả từ terminal:

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Explain JWT","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":8,"budget_remaining_usd":3.5e-05}}
```

### Exercise 4.3 — Rate limiting

Bản mẫu dùng **sliding window**. Limiter lưu timestamp các lượt gọi theo từng user, bỏ lượt đã nằm ngoài cửa sổ 60 giây, rồi kiểm tra số lượt còn lại trong cửa sổ. Role `user` có giới hạn 10 lượt/phút và role `admin` dùng quy tắc riêng 100 lượt/phút.

Trong vòng lặp dùng token của `student`, lượt 11 và 12 đều trả `429`. Trích response lượt 11:

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 29
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":29}}
```

### Exercise 4.4 — Cost guard

Đề xuất lưu tổng chi phí theo khóa Redis dạng `budget:<user_id>:<YYYY-MM>` với giới hạn **10 USD/người/tháng**. Trước khi gọi LLM, tính chi phí dự kiến dựa trên token đầu vào và giới hạn token đầu ra. Kiểm tra và giữ trước khoản dự kiến trong một thao tác nguyên tử để các request đồng thời dùng chung ngân sách. Khi vượt ngân sách, trả `402 Payment Required`. Khi có số token thực tế, ghi nhận chênh lệch và đặt hạn cho khóa theo kỳ tính ngân sách.

Rate limit giới hạn số lượt gọi trong một khoảng thời gian. Cost guard giới hạn tổng tiền, nên một số ít request tốn nhiều token vẫn có thể chạm ngân sách. Bản mẫu CP3 theo dõi chi phí theo ngày trong RAM, còn đây là thiết kế Redis theo tháng của Exercise 4.4.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Liveness và readiness

Khi chạy agent mẫu, `GET /health` trả `200 OK` và trạng thái liveness. `GET /ready` cũng trả `200 OK` khi ứng dụng đã khởi động. Liveness cho biết tiến trình còn hoạt động. Readiness cho biết instance đã sẵn sàng nhận traffic, tùy trạng thái khởi động và các dịch vụ phụ thuộc.

### Exercise 5.2 — Graceful shutdown

Gửi `POST /ask?question=Hello` tới agent mẫu, đợi khoảng nửa giây rồi gửi `SIGTERM` cho tiến trình Uvicorn. Log ghi `Shutting down` trước khi request `POST /ask` trả `200 OK`. Sau đó, lifespan chạy cleanup và ghi `Shutdown complete`.

### Exercise 5.3 — State của phiên

Nếu lưu lịch sử trong RAM, mỗi instance chỉ thấy các lượt hội thoại nó đã nhận và dữ liệu sẽ mất khi tiến trình khởi động lại. Bản production lưu phiên theo `session_id` trong Redis, để các instance đọc cùng lịch sử. Lưu session theo TTL cũng giúp giải phóng dữ liệu khi phiên hết hạn.

### Exercise 5.4 — Load balancing

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` trong `05-scaling-reliability/production/`. Nginx nhận traffic từ cổng 8080 và chuyển `POST /chat` cho các instance agent. Trong lần chạy thực tế, 5 request được chuyển lần lượt tới `instance-302c3a`, `instance-0ab23e`, `instance-b7eb58`, `instance-302c3a` và `instance-0ab23e`.

### Exercise 5.5 — Kiểm tra stateless

Kết quả `python test_stateless.py`:

```text
Total requests: 5
Instances used: {'instance-0ab23e', 'instance-b7eb58', 'instance-302c3a'}
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

Mỗi câu hỏi có một tin nhắn của người dùng và một câu trả lời. Lịch sử vẫn đủ 10 tin nhắn dù các lượt được xử lý bởi 3 instance. Phép thử kiểm tra chia sẻ phiên qua Redis giữa các replica. Stack đã được dừng sau khi kiểm tra.

## Part 6 — Production-ready agent

Chạy `python check_production_ready.py` đầy đủ trên Ubuntu WSL2, Python 3.12.16 và Docker 29.9.3. Image đo bằng script là **273 MB**. Khi Redis mất kết nối, `/ready` trả 503 và `/health` vẫn trả 200. Thử SIGTERM cho thấy request đang xử lý vẫn trả 200, và `docker stop` kết thúc với exit code 0 trong 1,2 giây.

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

Tôi chạy CP1–CP3 và gửi kết quả terminal. AI hướng dẫn, tổng hợp kết quả và hỗ trợ viết code Part 6.
