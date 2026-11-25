# Benchmark & Observability Report — Day 14

**Họ tên** Nguyễn Lâm Hoàng
**Ngày chạy** 25/11/2026 (GMT+7)
**Môi trường** Windows với Ubuntu WSL2, Python 3.12.16 và Docker Desktop 29.9.3. Mock LLM chạy local.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
| --- | --- | --- |
| p95 latency `/ask` | ≤ 500 ms | Đặt mục tiêu cho phần lớn lượt gọi và quan sát riêng phần đuôi bằng p99. |
| Error rate `/ask` | ≤ 2% | Giới hạn tỷ lệ request thất bại trong mỗi đợt load test. |
| Accuracy trên golden dataset | 100% và không regression | Bộ 23 câu bao phủ nội dung lab và là quality gate cho bản v2 đã sửa. |

## 2. Benchmark hiệu năng

### 2.1 Concurrency và latency

Agent v2, 300 request mỗi mức, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Số liệu lấy từ `reports/load_v2_c*.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4,34 | 196,1 | 232,7 | 1705,7 | 1,33% | PASS |
| 10 | 35,85 | 215,9 | 483,5 | 1672,7 | 0,33% | PASS |
| 50 | 36,75 | 680,9 | 3701,4 | 5307,8 | 1,00% | FAIL |
| 100 | 19,94 | 3527,3 | 7316,4 | 9948,3 | 1,33% | FAIL |

Throughput tăng tới 36,75 req/s ở concurrency 50 rồi giảm còn 19,94 req/s ở concurrency 100. Cả hai mức cao vi phạm ngưỡng p95. Mỗi đợt chỉ có 300 request và máy cũng đang tải image Docker cho phần observability, nên phép đo này không cô lập riêng các nguyên nhân gây chậm. p99 thể hiện độ chậm mà p50 khó phản ánh.

### 2.2 Tail latency

Mỗi mức chạy 300 request với concurrency 20 và cùng cấu hình lỗi. Số liệu lấy từ `reports/load_v2_slow_*.json`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
| --- | ---: | ---: | ---: |
| 0 | 234,8 | 321,8 | 357,7 |
| 0.03 | 376,3 | 964,6 | 1757,5 |
| 0.1 | 424,0 | 1722,3 | 1789,6 |

Trong lần đo này, **p99** thay đổi nhiều nhất khi tăng tỷ lệ request chậm từ 0 lên 0,1. Percentile phản ánh phần đuôi tốt hơn giá trị trung bình vì một nhóm nhỏ request chậm có thể bị làm mờ khi lấy trung bình trên tất cả request.

## 3. Benchmark chất lượng

Eval dùng cùng golden dataset, với lỗi ngẫu nhiên và độ trễ bất thường được tắt để tập trung so sánh chất lượng câu trả lời. Agent v2 đã sửa chạy trên cổng 8001 để tách khỏi load test của agent ở cổng 8002. File kết quả nằm trong `reports/eval_*.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
| --- | ---: | ---: | ---: |
| Accuracy | 1/23 (4,3%) | 21/23 (91,3%) | 23/23 (100,0%) |
| Avg tokens / câu | 57,5 | 109,0 | 115,4 |
| Tổng chi phí (USD) | 0.00040900 | 0.00076000 | 0.00080500 |
| Chi phí / câu đúng (USD) | 0.00040935 | 0.00003619 | 0.00003502 |
| Quality gate | FAIL | PASS | PASS |

| ID | Từ khóa bị thiếu | Thay đổi ở knowledge base |
| --- | --- | --- |
| `security-02` | token, hết hạn, chữ ký | Thêm mục JWT, giải thích chữ ký, thời điểm hết hạn và cách API key được xác minh. |
| `scaling-03` | CPU, memory, custom metrics | Thêm mục Kubernetes HPA mô tả các chỉ số dùng để điều chỉnh số replica. |

Retrieval dùng thêm token và tăng chi phí mỗi đợt eval, đồng thời cải thiện accuracy. Vì v2 trả lời đúng nhiều câu hơn, chi phí trên mỗi câu đúng giảm so với v1. Với CI, chạy `eval/run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` trên agent của nhánh cần kiểm tra. Bật yêu cầu job CI thành công trước khi merge. Script trả mã thoát khác 0 nếu thiếu accuracy hoặc có regression.

## 4. Observability stack

### 4.1 Dashboard dưới tải

Ảnh Grafana và số liệu truy vấn Prometheus được lấy trong đợt mô phỏng lỗi và request chậm. Một mẫu Prometheus ghi nhận **21,38 req/s**, p95 **1.896,5 ms**, trung bình **585,4 ms** và error rate **19,22%**. Khoảng cách giữa p95 và trung bình cho thấy một nhóm request chậm hơn đáng kể.

Nginx phân phối tương đối đều qua ba instance, lần lượt **7,07**, **7,13** và **7,18 req/s**. Input token đạt **1.209,09 token/s**, cao hơn output **690,91 token/s** vì đầu vào gồm câu hỏi và ngữ cảnh truy xuất. Gọi `/metrics` qua Nginx trả **404**, còn Prometheus truy cập endpoint trực tiếp qua mạng nội bộ Docker. [Ảnh Grafana](screenshots/grafana-dashboard.png)

### 4.2 Thí nghiệm và cảnh báo

| Thay đổi | Cảnh báo quan sát được | Thời gian quan sát | Panel liên quan |
| --- | --- | --- | --- |
| `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 101,7 giây từ khi áp dụng cấu hình kết hợp A+B | Error rate |
| `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | Thấy firing sau 35,4 giây. Điều kiện đã active từ lượt tải trước, nên đây không phải thời gian phát hiện từ trạng thái sạch. | Latency p95 |
| `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | 231,6 giây từ khi áp dụng cấu hình kết hợp C+D | Cost burn rate |
| Pause một replica | `AgentInstanceDown` | Thấy firing khi bắt đầu quan sát. Alert đã active từ trước khi pause, nên không xác định được thời gian phát hiện riêng của thao tác này. | Instances up |
| `AGENT_VERSION=v1` | Không ghi nhận alert mới do chất lượng | Metrics xác nhận 3 replica v1. Alert chi phí từ giai đoạn trước vẫn xuất hiện trong cửa sổ đo. | Version và Retrieval hit ratio |

Ảnh Prometheus xác nhận **`AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing**. `promtool test rules` báo `SUCCESS`. Để phát hiện suy giảm chất lượng khi đổi sang v1, chạy quality gate với golden dataset trước khi deploy và eval định kỳ sau deploy. [Ảnh Prometheus](screenshots/prometheus-alert-firing.png)

### 4.3 Trace chậm và trace lỗi

**Trace chậm** `ffb6cd9eb3c53b39fe90391e3ef80487` kéo dài **1.716,9 ms**. Trong các bước xử lý, `chat mock-llm-small` chiếm **1.694,3 ms** (98,7% tổng thời gian). ID khớp sự kiện `llm_call` trong log. [Ảnh trace chậm](screenshots/jaeger-slow-trace.png)

```json
{"ts":"2026-11-25T10:24:51.529573+00:00","level":"INFO","service":"observable-agent","instance":"5ee463e9c84e","event":"llm_call","trace_id":"ffb6cd9eb3c53b39fe90391e3ef80487","span_id":"76b187f96cf8da5a","request_id":"c61c40b3e784","model":"mock-llm-small","agent_version":"v2","input_tokens":70,"output_tokens":40,"cost_usd":0.000034,"llm_ms":1693.6}
```

**Trace lỗi** `de11304507cad5d39955a2bf97adf762` kéo dài **274,2 ms**, trả HTTP **503**. Span `chat mock-llm-small` kéo dài **82,5 ms** và API Jaeger ghi event `exception` với thông báo lỗi upstream mock. ID khớp sự kiện `llm_error` trong log. [Ảnh trace lỗi](screenshots/jaeger-error-trace.png)

```json
{"ts":"2026-11-25T10:25:50.579204+00:00","level":"INFO","service":"observable-agent","instance":"25f4f0a52a87","event":"llm_error","trace_id":"de11304507cad5d39955a2bf97adf762","span_id":"e7d6d4fd2f0a0017","request_id":"7ee506f416e2","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

Locust 2.47.0 chạy headless với 100 người dùng, tăng 10 người dùng/giây và chạy 2 phút cho mỗi mức. Locust chạy trong venv Windows và gọi Nginx qua `localhost:8080` vì Docker lỗi giải nén image Locust. Agent, Nginx, Grafana, Prometheus và Jaeger chạy bằng Docker Compose.

| Số instance | RPS `/ask` | p50 (ms) | p95 (ms) | p99 (ms) | Failures `/ask` |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 5,74 | 10.000 | 36.000 | 38.000 | 540/678 (79,65%) |
| 3 | 39,93 | 240 | 3.700 | 10.000 | 195/4.771 (4,09%) |

Các số lấy từ dòng `POST /ask` trong [scale_1_stats.csv](benchmark-results/scale_1_stats.csv) và [scale_3_stats.csv](benchmark-results/scale_3_stats.csv). Ở lần đo này, tăng replica cải thiện rõ thông lượng và p95. Tuy nhiên, p95 với 3 instance vẫn cao hơn ngưỡng 500 ms dùng ở load test local. Lỗi 504 của Nginx giảm từ 537 xuống 156 ở `/ask`, cho thấy thời gian chờ phản hồi từ upstream là một phần quan trọng của vấn đề. Phép đo này chưa cô lập được mức đóng góp của CPU, Docker Desktop và độ trễ mô phỏng. [Chi tiết lỗi ở 1 instance](benchmark-results/scale_1_failures.csv) · [Chi tiết lỗi ở 3 instance](benchmark-results/scale_3_failures.csv)

## 6. Kết luận

- p95 và p99 mô tả trải nghiệm ở phần đuôi mà median có thể bỏ qua.
- Đo chi phí trên mỗi câu đúng giúp so sánh các bản agent có chất lượng trả lời khác nhau.
- Quality gate trên cùng dataset giúp phát hiện regression dù agent vẫn đáp ứng SLO vận hành.

Khi đưa lên production, có thể theo dõi thêm tỷ lệ lỗi theo upstream và tỷ lệ request trả lời đúng trên một tập eval định kỳ để tách sự cố hạ tầng khỏi suy giảm chất lượng.
