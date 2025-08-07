# Test Suite

## Quick Start

### Setup
```bash
# Start PostgreSQL
docker-compose up -d db

# Set PYTHONPATH (required for all test runs)
export PYTHONPATH=/Users/jaidenreddy/Documents/projects/all_dreams/backend_dream:$PYTHONPATH

# Install test deps (if needed)
pip install pytest pytest-asyncio pytest-timeout
```

### Run Tests
```bash
# All tests
python -m pytest tests/

# Specific file
python -m pytest tests/test_dream_context.py

# Specific test
python -m pytest tests/test_dream_context.py::TestDreamContextWindow::test_creation

# Verbose with output
python -m pytest tests/ -xvs

# Pattern matching
python -m pytest tests/ -k "context"

# With timeout override
python -m pytest tests/ --timeout=30
```

## Writing Tests

### Standard Test
```python
import pytest
import pytest_asyncio

class TestMyFeature:
    def test_sync(self):
        assert 1 + 1 == 2
    
    @pytest.mark.asyncio
    async def test_async(self, db_session):
        result = await some_function(db_session)
        assert result is not None
```

### Real LLM Tests
```python
from llm_test_utils import LLMTestHelper, llm_integration_test

@llm_integration_test  # Auto: asyncio + timeout + API key check
async def test_with_real_llm():
    llm = LLMTestHelper.create_test_llm("gpt-4o-mini")
    result = await llm.generate_response([{"role": "user", "content": "test"}])
    assert result is not None

# Or use fixtures
async def test_with_llm_fixture(test_llm):
    result = await test_llm.generate_response([{"role": "user", "content": "test"}])
    assert result is not None
```

### Quick LLM Testing
```python
from llm_test_utils import quick_llm_test, quick_structured_llm_test

# Simple
response = await quick_llm_test("What is 2+2?")

# Structured
schema = {"type": "object", "properties": {"answer": {"type": "number"}}}
result = await quick_structured_llm_test("What is 2+2? Return JSON.", schema)
```

## Environment Setup

### PostgreSQL Database
- **Host**: localhost:5433
- **Credentials**: campfire/campfire
- **Test DB**: `campfire_test` (auto-created/destroyed)

### OpenAI API Key
Tests automatically load from `/Users/jaidenreddy/Documents/projects/all_dreams/backend_dream/.env`
- Must start with `sk-proj-zrtT`
- LLM tests auto-skip if not available

## Fixtures Available

- `db_session` - PostgreSQL session with auto-rollback
- `test_llm` - Real OpenAI LLM (gpt-4o-mini)
- `test_llm_fast` - gpt-4o-mini
- `test_llm_smart` - gpt-4o
- `all_test_llms` - Dict of all LLM variants

## Decorators

- `@pytest.mark.asyncio` - For async tests
- `@requires_llm` - Skip if no OpenAI API key
- `@llm_integration_test` - Combines asyncio + 30s timeout + API key check

## Troubleshooting

**Import errors**: Check PYTHONPATH
```bash
export PYTHONPATH=/Users/jaidenreddy/Documents/projects/all_dreams/backend_dream:$PYTHONPATH
```

**DB errors**: Start PostgreSQL
```bash
docker-compose up -d db
```

**Timeout errors**: Use longer timeout
```bash
python -m pytest tests/ --timeout=30
# or @pytest.mark.timeout(30) on specific tests
```

**LLM tests skipped**: Check `.env` has correct `OPENAI_API_KEY=sk-proj-zrtT...`

**Debug**: Use `-s` for prints, `--pdb` for debugger
```bash
python -m pytest tests/ -s --pdb
```