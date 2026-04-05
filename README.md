# Odoo Tutor
An interactive AI-powered learning tool designed to assist users in mastering Odoo functionalities by assigning practical exercises and providing real-time feedback within an Odoo staging environment.

## Quick Start

1. **Clone the repository:**

    ```sh
    git clone <repository-url>
    cd odoo-tutor-backend
    ```
2. **Create a `.env` file** in the project root with the following variables:

    ```env
    OPENAI_API_KEY=sk-...your-openai-key...
    API_KEY=your_super_secret_key_123
    ODOO_BACKEND_URL=https://odooconcept-at-18-0-odoo-tutor-tests-21572478.dev.odoo.com
    ```

    - `OPENAI_API_KEY`: Your OpenAI API key for GPT-4o.
    - `API_KEY`: Required in the `x-api-key` header for all requests.
    - `ODOO_BACKEND_URL`: The Odoo backend instance used for validation.

3. **Build and start the services using Docker Compose:**

    ```sh
    docker-compose build --no-cache ms_ai_dev  
    ```

    - Optional: build production container
    ```sh
    docker-compose build --no-cache ms_ai 
    ```
4. Run services
  ```sh
    docker-compose up ms_ai_dev
  ```
5. Run Redis
  ```sh
    docker-compose up -d redis
  ```
  
6. **Service URLs:**
    - AI Service: `http://localhost:8001`
    - Quotation Service: `http://localhost:8000`

## Run  linter and code formatter
 ```sh
    black .  
    isort .
    ruff check --fix .
 ```
 - Run pre-commit (optional)
 ```sh
    pre-commit run --all-files
 ```

 ## Run test
 - Create a virtual enviroment and activate it:
  python -m venv venv
  venv\Scripts\Activate.ps1
 - Run test with coverage
```sh
  pytest test/ --cov=ms_ai/app --cov-report=html
```
- Run test without coverage
```sh
  pytest --cache-clear test/ -v
```
- Run locust test for load testing
```sh
  locust -f load_tests/test_locust_websocket.py --host=http://localhost:8002
```

## Endpoints

### AI Service

- `GET /` — Health check.
- `POST /chat` — Send a message to the AI model and receive a response.
- `GET /validate_exercise` — Validate an exercise against the Odoo backend.

### Quotation Service

- `GET /` — Health check.
- `POST /generate_quote` — Generate a quotation.

## Example: Chat Endpoint

```sh
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "message": "How do I create a sales quotation in Odoo?",
    "context": {"model": "sale.order"}
  }'
```

**Response:**
```json
{
  "response": "...AI answer...",
  "exercise_id": 1
}
```

## Environment Variables

- All configuration is managed via `.env` and loaded automatically by Docker Compose.
- To change the Odoo backend, update `ODOO_BACKEND_URL` in `.env` and restart the service.

## Multilingual Support

- The AI model supports multilingual queries (e.g., English, Spanish).
- To add exercises in multiple languages, add fields like `goal_en`, `goal_es` in `content/exercises.json`.

## Error Handling

| HTTP Status | Meaning            | Trigger                                   |
|-------------|--------------------|-------------------------------------------|
| 200         | ✅ OK               | Message sent and response received        |
| 422         | ❌ Validation Error | Missing or invalid "message" field        |
| 500         | 💥 Server Error     | Internal error or OpenAI service failure  |

## Dependencies

### AI Service (`ms_ai`)
- fastapi
- uvicorn
- python-dotenv
- langchain-openai
- langchain-core
- sentence-transformers

### Quotation Service (`ms_pricing`)
- fastapi
- uvicorn
- pandas
- openpyxl

## License
  
This project is licensed under the MIT License.
