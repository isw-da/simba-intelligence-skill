# Post-Install Configuration

After deploying Simba Intelligence and configuring an LLM provider, follow
these steps to connect data and start querying.

---

## 1. Create a data connection

A data connection provides Simba Intelligence with access to a database.

1. Navigate to **Data Connections** in the SI UI
2. Click **Create Connection**
3. Select the connector type for your database
4. Provide credentials and connection parameters:
   - Hostname / account locator
   - Port (if non-default)
   - Database name / catalog / warehouse
   - Schema (optional — can scope to specific schemas)
   - Username and password (or service account)
5. Click **Test Connection** to verify connectivity
6. **Save**
7. Wait for initial metadata discovery to complete (time depends on catalog size)

### Supported databases

Snowflake, PostgreSQL, SQL Server, BigQuery, Oracle, MySQL, Databricks,
and other JDBC-compatible sources.

### Platform-specific tips

| Database | Recommendation |
|---|---|
| Snowflake | Provide account locator + region, dedicated warehouse, role with `USAGE` + `SELECT` |
| PostgreSQL | Use a read replica endpoint to avoid OLTP impact |
| SQL Server | Use a read replica or reporting instance |
| BigQuery | Service account with `roles/bigquery.dataViewer` + project `metadataViewer` |
| Oracle | Read-only user with `SELECT` on target schemas |
| Databricks | Use a SQL Warehouse endpoint with a service principal |

### Security recommendations

- Use a dedicated service account for SI, not a personal user
- Grant read-only access (SELECT only) to analytical schemas
- Avoid granting access to entire databases when schema-level scoping is possible
- Rotate credentials per your organisation's policy

---

## 2. Create a data source with the Data Source Agent

The Data Source Agent uses AI to automatically build a governed data source
from a connected database.

1. Navigate to `/data-source-agent`
2. Select the connection created in Step 1
3. Provide input (one or both):
   - **Text description**: Describe the data you need in business terms
   - **Image upload**: Upload a dashboard mockup or screenshot (PNG/JPG, max 10MB)
4. The agent will:
   - Inspect schema metadata
   - Propose table selections and join relationships
   - Assemble a data source definition with fields and metrics
5. Review the generated definition:
   - Rename fields for clarity
   - Hide fields that should not be exposed
   - Verify join relationships
6. **Approve to publish**

### Example descriptions

```
Sales performance analysis:
Revenue by product category and region, monthly and quarterly trends,
top-performing sales representatives, customer segmentation.
```

```
Inventory tracking:
Current stock levels by warehouse, product movement history,
reorder points, supplier performance metrics.
```

### Tips

- Keep the first data source narrow — focus on one analytical domain
- One-to-many joins cause metric inflation (e.g. revenue doubles when
  joining orders to order line items). Set the grain at the many-side
  table or create separate data sources per grain.
- Enforce naming conventions early (e.g. `revenue_total`, `customer_churn_rate`)

### Prerequisites

The Data Source Agent requires:
- At least one LLM provider configured with Chat + Embeddings enabled
- At least one data connection configured and accessible
- The `ROLE_CREATE_SOURCES` permission or higher

If any prerequisite is missing, the agent will display a message directing
the user to the configuration page.

---

## 3. Query in the Playground

The Playground is the natural language query interface.

1. Navigate to `/playground`
2. Select a published data source from the dropdown
3. Ask questions in plain English

### Example queries

```
What is total revenue this quarter vs the same quarter last year?
Show top 15 customers by trailing 90-day revenue.
Break down churn by region and customer segment.
Which products had declining monthly revenue for the last 4 months?
```

### How it works

When you ask a question:
1. The LLM interprets the question against the data source schema
2. A SQL query is generated and executed against the connected database
3. Results are returned with a natural language explanation

### Session behaviour

- Conversational context is maintained within a browser session
- Follow-up questions reference previous context (e.g. "break that down by region")
- Sessions are NOT saved — context resets on page refresh or browser close
- Chat history cannot be exported or shared

### Feedback

Each response includes thumbs up / thumbs down buttons. Feedback helps
improve AI performance for similar queries.
