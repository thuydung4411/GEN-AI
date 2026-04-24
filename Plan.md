v# Ke Hoach Refactor: UI Thong Nhat, Backend Tach Lane, San Sang Cho Agent PEV

## 1. Muc tieu

Refactor he thong hien tai tu mo hinh:

- UI tach `Structured Datasets` va `Knowledge Base`
- API tach `/v1/datasets/*` va `/v1/knowledge/*`
- chat dang nghieng ve RAG

sang mo hinh dai han:

- UI thong nhat cho upload, danh sach asset, va chat
- backend van tach ro 2 lane xu ly:
  - `structured lane` cho `csv/xlsx/xls`
  - `knowledge lane` cho `pdf/docx/txt/md`
- co `Asset API` thong nhat de frontend khong can biet lane ben duoi
- chat layer san sang de them `router` va `agent PEV`
- agent co the quyet dinh:
  - `rag`
  - `sql`
  - `hybrid`
  - `clarification`

## 2. Pham vi cua ban refactor nay

Ban refactor nay khong nham xay full agent ngay lap tuc. Muc tieu la:

1. lam sach boundary giua UI va backend
2. thong nhat asset model o lop API/public contract
3. giu lane tach biet o ingestion va execution
4. chuan bi san cho Phase 3 chat va Phase sau la router/agent

Khong lam trong dot nay:

- multi-agent
- web browsing
- autonomous write actions
- planner phuc tap nhieu vong lap
- dashboard BI polish nang

## 3. Hien trang repo

He thong hien tai da co nen tang tuong doi tot:

- auth va workspace isolation
- upload dataset
- upload knowledge
- ingestion worker cho 2 lane
- metadata dataset, preview/profile
- knowledge parsing/chunking
- chat service va RAG service o muc dau

Nhung van co 3 van de kien truc:

1. UI bat user phai thay 2 lane rieng
2. frontend dang phu thuoc truc tiep vao route dataset/knowledge
3. boundary chat/tool chua tach ro de sau nay dat router/agent len tren

## 4. Dinh huong kien truc

### 4.1. Nguyen tac cot loi

- UI co the thong nhat, nhung backend khong duoc tron lane.
- Agent quyet dinh route, nhung khong thay the duoc execution contracts.
- `RAGService` chi lam text retrieval va grounded generation.
- `TextToSQLService` chi lam schema introspection, SQL generation, SQL validation, va DuckDB execution.
- `RouterService` hoac `AgentService` moi la noi quyet dinh goi lane nao.
- Moi asset, job, query, va tool call deu phai gan `workspace_id`.

### 4.2. Mo hinh dich

- `web`
  - 1 upload form
  - 1 asset list
  - 1 chat app
- `api`
  - `Asset API` thong nhat
  - legacy `datasets` va `knowledge` routes chi con la compatibility layer trong thoi gian chuyen doi
  - chat orchestration
  - router/agent layer
- `worker`
  - generic job dispatcher
  - structured processor
  - knowledge processor
- `postgres`
  - asset metadata
  - jobs
  - chat sessions/messages
  - route decisions
  - agent runs
- `duckdb`
  - structured query execution
- `pgvector`
  - knowledge retrieval

## 5. Tai sao van phai tach lane

UI thong nhat khong co nghia la execution thong nhat.

`csv/xlsx/xls` va `pdf/docx/txt/md` khac nhau o:

- parser
- metadata
- storage/query model
- validation
- provenance
- test strategy
- risk model

Structured lane can:

- sheet discovery
- schema inference
- preview/profile
- materialize vao DuckDB
- query read-only

Knowledge lane can:

- text extraction
- chunking
- embedding
- vector retrieval
- citations

Neu gom vao mot service "sieu tong quat", sau nay agent se kho debug hon, khong de hon.

## 6. Public contract dich

### 6.1. Asset kinds

- `dataset`
- `knowledge`

### 6.2. Public APIs moi

- `POST /v1/assets/upload`
- `GET /v1/assets`
- `GET /v1/assets/{id}`
- `DELETE /v1/assets/{id}`
- `GET /v1/assets/{id}/preview` cho dataset
- `GET /v1/assets/{id}/profile` cho dataset

Chat APIs giu nguyen huong:

- `POST /v1/chat/sessions`
- `GET /v1/chat/sessions`
- `GET /v1/chat/sessions/{id}`
- `POST /v1/chat/sessions/{id}/messages`

Legacy routes du kien con ton tai tam thoi:

- `POST /v1/datasets/upload`
- `GET /v1/datasets`
- `DELETE /v1/datasets/{id}`
- `POST /v1/knowledge/upload`
- `GET /v1/knowledge`
- `DELETE /v1/knowledge/{id}`

### 6.3. Public response types

- `AssetSummary`
- `AssetDetail`
- `UploadAssetResponse`
- `AssetJobSummary`
- `RouteDecision`
- `ToolExecutionTrace`
- `VerificationResult`

## 7. Contract route va evidence

Moi answer trong chat ve sau phai co:

- `route`: `rag | sql | hybrid | clarification`
- `retrieval_used`: `true | false`
- `sql_used`: `true | false`
- `evidence`

Evidence theo tung route:

- `rag`
  - document/asset title
  - chunk id
  - page/section neu co
  - quote/snippet
- `sql`
  - asset id
  - sheet/table
  - SQL da chay hoac SQL summary
  - row count
  - aggregates quan trong
- `hybrid`
  - ca citation text va SQL provenance

## 8. Risk assessment

- **Risk 1: Big-bang refactor lam gay flow upload hien tai**
  - **Mitigation**: lam theo facade truoc, legacy routes giu nguyen trong mot vai phase.

- **Risk 2: Asset API thong nhat nhung backend dispatch sai lane**
  - **Mitigation**: classify theo extension + MIME + parser fallback; co test matrix cho tung loai file.

- **Risk 3: Worker generic job lam mat idempotency**
  - **Mitigation**: cleanup metadata/chunk cu truoc khi insert, status transition ro rang, test retry/reprocess.

- **Risk 4: Nhiet tinh them Text-to-SQL vao RAG service**
  - **Mitigation**: tach service boundary ngay tu dau; `RAGService` khong duoc chua SQL execution logic.

- **Risk 5: UI thong nhat nhung provenance mo ho**
  - **Mitigation**: asset list co badge kind; chat response hien thi route va evidence.

- **Risk 6: Legacy va new API chay song song gay drift**
  - **Mitigation**: route moi goi vao service chung; legacy route chi la wrapper.

- **Risk 7: Agent sau nay kho debug**
  - **Mitigation**: dat `router baseline` truoc, `PEV agent` sau; luu route decision va tool trace.

## 9. Execution plan theo phase

### Phase 0: Baseline va freeze

#### Muc tieu

Chot trang thai hien tai truoc khi refactor de khong bi "sua xong ma khong biet da vo cai gi".

#### Cong viec

- Giu test Phase 1 va Phase 2 dang xanh.
- Ghi ro endpoints hien tai va diem se deprecate.
- Chot state hien tai cua:
  - `DatasetService`
  - `KnowledgeService`
  - `worker` structured lane
  - `worker` knowledge lane
  - `dashboard-shell`

#### Verify

- `api/tests/test_phase1_api.py` pass
- `worker/tests/test_ingestion.py` pass
- parser manual probe cho CSV/XLSX/TXT pass

#### Review gate

- Repo o baseline on dinh, co the refactor tung phase.

#### Rollback

- Khong can rollback code, chi can dung lai o baseline commit.

---

### Phase 1: Tao Asset API facade

#### Muc tieu

Frontend bat dau co mot hop dong thong nhat ma chua can thay doi schema ben duoi ngay lap tuc.

#### Cong viec

- Tao `api/app/api/routes/assets.py`
- Tao `api/app/services/assets.py`
- Tao `api/app/schemas/assets.py`
- `POST /v1/assets/upload`
  - detect `asset_kind`
  - route noi bo sang `DatasetService` hoac `KnowledgeService`
- `GET /v1/assets`
  - merge danh sach dataset va knowledge
  - sort theo `created_at desc`
- `GET /v1/assets/{id}`
  - tra detail theo kind
- `DELETE /v1/assets/{id}`
  - dispatch delete theo kind

#### Decisions

- Frontend khong duoc tu phan route theo extension nua sau phase nay.
- Legacy routes van ton tai.

#### Test bat buoc

- upload `csv` qua `/v1/assets/upload` tao dataset job
- upload `pdf` qua `/v1/assets/upload` tao knowledge asset/job
- `GET /v1/assets` tra mixed list dung `kind`
- delete dataset qua `/v1/assets/{id}`
- delete knowledge qua `/v1/assets/{id}`
- workspace isolation cho mixed list

#### Review gate

- Frontend co the chi dung `/v1/assets/*` ma van hoat dong day du.

#### Rollback

- Quay ve routes cu `/v1/datasets/*` va `/v1/knowledge/*`.

---

### Phase 2: Generic asset domain model

#### Muc tieu

Lam sach domain de khong song mai voi hai root entity song song trong public model.

#### Schema dich

- `assets`
  - `id`
  - `workspace_id`
  - `kind`
  - `title`
  - `original_filename`
  - `mime_type`
  - `status`
  - `created_at`
  - `updated_at`
- `asset_versions`
  - `id`
  - `asset_id`
  - `version_number`
  - `storage_backend`
  - `storage_path`
  - `file_size_bytes`
  - `checksum_sha256`
  - `created_at`
- `ingestion_jobs`
  - `id`
  - `workspace_id`
  - `asset_id`
  - `asset_version_id`
  - `asset_kind`
  - `status`
  - `error_message`
  - `created_at`
  - `updated_at`

Lane-specific tables giu rieng:

- `dataset_sheets`
- `column_profiles`
- `knowledge_chunks`

#### Cong viec

- Tao migration additive cho `assets` va `asset_versions`
- Backfill tu `datasets` va `knowledge_assets`
- Refactor repositories sang generic asset root
- Refactor service mapping sang `AssetSummary`/`AssetDetail`
- Chua xoa bang cu trong phase nay

#### Test bat buoc

- backfill row count dung
- asset list sau backfill khong mat du lieu
- ingestion job moi link dung `asset_id`
- delete asset khong xoa nham workspace khac

#### Review gate

- Co the doc va thao tac asset thong qua model generic ma khong can biet bang cu.

#### Rollback

- Van giu bang cu va route cu de fallback.

---

### Phase 3: Worker generic dispatcher

#### Muc tieu

Worker chi claim job generic, sau do dispatch sang processor dung theo `asset_kind`.

#### Cong viec

- Refactor `worker/app/main.py`
- Tao:
  - `StructuredLaneProcessor`
  - `KnowledgeLaneProcessor`
- `claim_next_job()` chi tra generic fields
- Structured processor:
  - tai file
  - parse bang `TabularParser`
  - cleanup `DatasetSheet`/`ColumnProfile` cu
  - materialize DuckDB
  - update asset/job status
- Knowledge processor:
  - tai file
  - parse bang `KnowledgeParser`
  - cleanup `KnowledgeChunk` cu
  - embed/index
  - update asset/job status

#### Edge cases bat buoc

- file rong
- parser loi
- retry sau job fail
- process lai cung version
- local path/Windows path handling

#### Test bat buoc

- dataset happy path
- knowledge happy path
- dataset fail path
- knowledge fail path
- idempotent reprocess
- status `pending -> processing -> ready|failed`

#### Review gate

- Worker khong can biet dataset/knowledge route cu, chi can generic asset job.

#### Rollback

- Neu can, giu dispatcher cu trong mot branch/feature flag tam thoi.

---

### Phase 4: UI dashboard thong nhat

#### Muc tieu

Bo 2 khoi upload rieng tren dashboard, chuyen sang 1 giao dien thong nhat nhung van giu badge `Dataset`/`Knowledge`.

#### Cong viec

- Refactor [web/app/dashboard/dashboard-shell.tsx](/d:/GEN%20AI/web/app/dashboard/dashboard-shell.tsx)
- Refactor [web/lib/api/client.ts](/d:/GEN%20AI/web/lib/api/client.ts)
- Tao 1 upload form:
  - accept `.csv,.xlsx,.xls,.pdf,.docx,.txt,.md`
- Sau upload:
  - goi `/v1/assets/upload`
  - backend tu classify lane
- Tao 1 asset list:
  - badge `Dataset` / `Knowledge`
  - status chip
  - action preview/profile neu la dataset
  - action view citations/search status neu la knowledge

#### UX decisions

- User co the khong thay "lane"
- User van thay "kind" de biet asset nay dung cho muc dich nao
- Chat van la 1 entry point chung

#### Test bat buoc

- upload moi loai file tu 1 form duy nhat
- asset list mixed hien dung
- delete asset hoat dong
- refresh status hoat dong

#### Review gate

- Dashboard chi con 1 luong asset chung.

#### Rollback

- Giu component cu sau feature flag den khi UI moi on.

---

### Phase 5: Chat boundary refactor

#### Muc tieu

Dat boundary dung de sau nay them router/agent ma khong lam ban service layer.

#### Cong viec

- Giu `RAGService` chi phu trach:
  - query embedding
  - vector retrieval
  - grounded prompt
  - citations
- Tao moi:
  - `TextToSQLService`
  - `RouterService`
  - hoac `ChatOrchestratorService`
- `TextToSQLService` phai lo:
  - schema introspection
  - SQL generation
  - SQL validation
  - read-only enforcement
  - DuckDB execution
  - result formatting
- `ChatService` chi lam orchestration:
  - validate session/workspace
  - goi router
  - goi service dung
  - save message lifecycle

#### Tuyet doi khong lam

- khong dua Text-to-SQL vao `RAGService`
- khong de chat route decision nam lan trong UI

#### Test bat buoc

- `RAGService` van pass retrieval tests
- `TextToSQLService` co test safety chi cho `SELECT`
- `ChatService` co metadata `route`

#### Review gate

- He thong co the ho tro them `sql` ma khong pha `rag`.

#### Rollback

- Neu SQL path chua on, chat co the chay `rag-only` bang config.

---

### Phase 6: Router baseline

#### Muc tieu

Them lop quyet dinh co kiem soat truoc khi len full agent.

#### Route outputs

- `rag`
- `sql`
- `hybrid`
- `clarification`

#### Cong viec

- Tao `RouterService`
- Baseline co the la:
  - rule-based + LLM classifier nhe
- Input:
  - user question
  - asset inventory trong workspace
  - dataset availability
  - knowledge availability
- Output:
  - `route`
  - `reason`
  - `confidence`
  - `tools_to_call`

#### Test bat buoc

- cau hoi dinh nghia -> `rag`
- cau hoi tong/avg/top/filter -> `sql`
- cau hoi can rule + tinh toan -> `hybrid`
- cau hoi mo ho -> `clarification`

#### Review gate

- Chat response co the hien `Route: RAG | SQL | Hybrid`.

#### Rollback

- fallback ve route hardcoded theo feature flag.

---

### Phase 7: Agent PEV

#### Muc tieu

Nang tu router len agent `Plan -> Execute -> Verify`.

#### Tool registry v1

- `list_assets`
- `get_dataset_schema`
- `get_dataset_profile`
- `preview_rows`
- `run_duckdb_sql`
- `search_knowledge`
- `get_knowledge_context`
- `ask_for_clarification`

#### PEV flow

- `Plan`
  - nhan dang loai cau hoi
  - chon route/tool chain
- `Execute`
  - goi tool theo plan
- `Verify`
  - kiem tra answer co can cu that khong
  - neu la SQL, so lieu co khop tool output khong
  - neu la hybrid, rule text va ket qua tinh toan co nhat quan khong

#### Test bat buoc

- tool selection dung
- khong loop vo han
- khong cross-workspace leak
- khong goi write action
- co trace tung step

#### Review gate

- Agent quyet dinh khi nao dung RAG, khi nao dung SQL/tool, khi nao dung ca hai.

#### Rollback

- Tat agent, quay lai router baseline.

---

### Phase 8: Legacy cleanup va deploy readiness

#### Muc tieu

Xoa debt do compatibility layer de lai va chot he thong cho staging.

#### Cong viec

- Deprecate va xoa dan `/v1/datasets/*`, `/v1/knowledge/*` neu da cutover xong
- Don repositories/service wrappers cu
- Cap nhat README, runbook, env docs
- Them smoke test:
  - upload asset
  - ingest
  - list assets
  - chat route rag/sql/hybrid

#### Review gate

- UI thong nhat hoat dong
- backend tách lane ro rang
- router/agent co the hoat dong ma khong phai sua ingestion core

## 10. Acceptance criteria tong

- User co 1 dashboard thong nhat cho asset va chat
- Backend van tach lane xu ly dung cho structured va knowledge
- Frontend khong con phu thuoc truc tiep vao dataset/knowledge routes
- Co `/v1/assets/*` lam public contract chinh
- Worker xu ly generic asset jobs
- Chat layer co boundary sach de them router/agent
- Agent co the quyet dinh `rag | sql | hybrid | clarification`
- Moi response quan trong deu co provenance/evidence
- Khong co workspace leak

## 11. Thu tu trien khai khuyen nghi

1. Phase 0: Baseline va freeze
2. Phase 1: Asset API facade
3. Phase 2: Generic asset domain model
4. Phase 3: Worker generic dispatcher
5. Phase 4: UI dashboard thong nhat
6. Phase 5: Chat boundary refactor
7. Phase 6: Router baseline
8. Phase 7: Agent PEV
9. Phase 8: Legacy cleanup va deploy readiness

## 12. Cau lenh review gate

- `duyet phase 1, lam phase 1`
- `duyet phase 2, lam phase 2`
- `duyet phase 3, lam phase 3`

Moi phase phai dung lai de review truoc khi sang phase tiep theo.
