# Báo Cáo Lab: Xây Dựng MCP Server Cho SQLite (FastMCP)
Nguyễn Xuân Hải - 2A202600245
## 1) Mục tiêu

Xây dựng một MCP server bằng FastMCP, kết nối SQLite và cung cấp đúng 3 tools:

- `search`
- `insert`
- `aggregate`

Ngoài ra, server phải expose schema dưới dạng MCP resources:

- `schema://database`
- `schema://table/{table_name}`

Project này dùng dataset `TFT_Challenger_MatchData.csv` và import vào SQLite thành bảng `tft_matches` để demo.

## 2) Dữ liệu và mô hình

- Nguồn dữ liệu: `TFT_Challenger_MatchData.csv`
- Bảng SQLite: `tft_matches`
- Các cột:
  - `id` (INTEGER, PRIMARY KEY)
  - `gameId` (TEXT)
  - `gameDuration` (REAL)
  - `level` (INTEGER)
  - `lastRound` (INTEGER)
  - `Ranked` (INTEGER)
  - `ingameDuration` (REAL)
  - `combination` (TEXT)
  - `champion` (TEXT)

Ghi chú: `combination` và `champion` được lưu dạng chuỗi (string) đúng theo CSV gốc.

## 3) Cấu trúc thư mục

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  test/
    test_server.py
image/
TFT_Challenger_MatchData.csv
.codex/config.toml
```

## 4) Cài đặt và chạy nhanh

### 4.1 Tạo môi trường Python và cài FastMCP

Từ thư mục repo:

```bash
python3 -m venv .venv
.venv/bin/pip install fastmcp
```

Kiểm tra:

```bash
.venv/bin/python -c "import fastmcp; print('fastmcp ok')"
```

### 4.2 Tạo/seed database

DB nằm ở `implementation/sqlite_lab.db`. Khi MCP tool chạy lần đầu, DB cũng sẽ tự được tạo/seed (nếu đang trống).

Nếu muốn reset và seed lại:

```bash
.venv/bin/python -c "from implementation.init_db import create_database; print(create_database(reset=True, seed_limit=5000))"
```

Ghi chú về hiệu năng:

- CSV ~ 80k dòng, nên mặc định seed theo `seed_limit` (ví dụ 5000) để demo nhanh.
- Nếu muốn seed toàn bộ CSV: dùng `seed_limit=None` (sẽ chậm hơn).

### 4.3 Chạy unit test và verify

Unit tests:

```bash
.venv/bin/python -m unittest implementation.test.test_server
```

Script verify (demo nhanh các tool/resource và một case lỗi):

```bash
.venv/bin/python implementation/verify_server.py
```

## 5) Mô tả tools và resources

### 5.1 Tool `search`

Mục đích: truy vấn dữ liệu theo bảng, filter, sort, phân trang.

Các tham số chính:

- `table`: tên bảng, hiện dùng `tft_matches`
- `filters`: list các điều kiện, dạng `{"column": "...", "op": "...", "value": ...}`
- `columns`: danh sách cột cần trả về (bỏ qua thì trả hết)
- `limit`, `offset`: phân trang
- `order_by`, `descending`: sắp xếp

Validation:

- reject table/column không tồn tại
- reject operator không hỗ trợ (`=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`)
- query dùng placeholder `?` để tránh SQL injection

### 5.2 Tool `insert`

Mục đích: chèn một record vào bảng.

Validation:

- reject `values` rỗng
- reject cột không tồn tại
- trả về payload đã insert (kèm `inserted_id`)

### 5.3 Tool `aggregate`

Mục đích: thống kê dữ liệu theo `metric` và tuỳ chọn `group_by`.

Hỗ trợ:

- `count`, `avg`, `sum`, `min`, `max`

Validation:

- reject metric không hỗ trợ
- với `avg/sum/min/max` bắt buộc có `column`
- reject group_by/column không tồn tại

### 5.4 Resources

- `schema://database`: trả về schema toàn bộ DB
- `schema://table/tft_matches`: trả về schema của bảng `tft_matches`

## 6) Cấu hình và test bằng Codex (khuyến nghị)

Project đã có sẵn cấu hình ở `.codex/config.toml` để Codex dùng đúng Python trong venv:

```toml
[mcp_servers.sqlite_lab]
command = "/home/nxhai/AI_thucchien/Day26-Track3-MCP-tool-integration/.venv/bin/python"
args = ["/home/nxhai/AI_thucchien/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py"]
```

Sau khi chỉnh config, restart Codex để nó reload MCP servers.

### 6.1 Kịch bản demo (copy/paste)

1) `search` (filter + limit):

```json
{"table":"tft_matches","filters":[{"column":"Ranked","op":"=","value":1}],"limit":5}
```

2) `search` (columns + order + pagination):

```json
{"table":"tft_matches","filters":[{"column":"Ranked","op":"=","value":1}],"columns":["gameId","Ranked","gameDuration"],"order_by":"gameDuration","descending":false,"limit":5,"offset":5}
```

3) `insert`:

```json
{"table":"tft_matches","values":{"gameId":"LOCAL_DEMO","gameDuration":1234.5,"level":8,"lastRound":30,"Ranked":1,"ingameDuration":1200.0,"combination":"{}","champion":"{}"}}
```

4) `aggregate`:

```json
{"table":"tft_matches","metric":"count"}
```

```json
{"table":"tft_matches","metric":"avg","column":"level","group_by":"Ranked"}
```

5) Resources:

- đọc `schema://database`
- đọc `schema://table/tft_matches`

6) Case lỗi (để chứng minh validation):

- table sai:

```json
{"table":"missing_table"}
```

- column sai:

```json
{"table":"tft_matches","filters":[{"column":"nope","op":"=","value":1}]}
```

- op sai:

```json
{"table":"tft_matches","filters":[{"column":"Ranked","op":"between","value":[1,2]}]}
```

- insert rỗng:

```json
{"table":"tft_matches","values":{}}
```

## 7) Test bằng Inspector (tuỳ chọn)

Nếu dùng MCP Inspector:

```bash
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector \
  /home/nxhai/AI_thucchien/Day26-Track3-MCP-tool-integration/.venv/bin/python \
  /home/nxhai/AI_thucchien/Day26-Track3-MCP-tool-integration/implementation/mcp_server.py
```

Trong Inspector, kiểm tra:

- tools xuất hiện: `search`, `insert`, `aggregate`
- resources xuất hiện: `schema://database`, `schema://table/{table_name}`
- gọi thử đúng và sai theo mục (6.1)

## 8) Chụp screenshot làm minh chứng 

### 8.1 Chụp ảnh (đủ minh chứng rubric)

Thư mục ảnh minh chứng: `image/` (đã có sẵn trong repo).

- `image/Giao_dien_Codex.png`: giao diện Codex/khung chat
- `image/search.png`: demo `search`
- `image/insert.png`: demo `insert`
- `image/aggregate.png`: demo `aggregate`
- `image/resource_schema.png`: demo đọc resource schema
- `image/error_case.png`: demo input lỗi và message error rõ ràng

1) Ảnh tool discovery:
   - chụp đoạn chat thể hiện Codex đã gọi được `sqlite_lab.search`/`sqlite_lab.insert`/`sqlite_lab.aggregate` (hoặc Codex liệt kê được danh sách tools của server).

2) Ảnh resource discovery:
   - chụp đoạn chat thể hiện đọc được `schema://database` hoặc `schema://table/tft_matches` và trả về schema JSON.

3) Ảnh một tool call hợp lệ có dữ liệu trả về:
   - ví dụ `search` có `limit/offset/order_by` và trả về `rows`.

4) Ảnh một tool call có side effect:
   - `insert` thành công (chụp phần `inserted_id` và `values`).

5) Ảnh một tool call không hợp lệ và error rõ ràng:
   - ví dụ table sai (`missing_table`) hoặc op sai (`between`).

### 8.2 Hướng dẫn kịch bản chụp screenshot bằng Codex 

1) Reset DB để số liệu “đẹp” và tránh side effects cũ:

```bash
.venv/bin/python -c "from implementation.init_db import create_database; print(create_database(reset=True, seed_limit=2000))"
```

2) Restart Codex.
3) Lần lượt gửi các prompt/demo ở mục (6.1). Khi chat, nên ghi rõ tool name, ví dụ:

`Use MCP server sqlite_lab. Call tool search with: {...}`

4) Sau mỗi bước quan trọng (discovery / valid call / insert / error), chụp 1 ảnh.
