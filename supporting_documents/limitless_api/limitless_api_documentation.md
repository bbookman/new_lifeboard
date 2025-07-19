# Limitless API Documentation

## Endpoints

### List Lifelogs
- **GET** `/v1/lifelogs`
- Get recent Lifelogs from your Pendant, search specific date ranges, sort, and paginate.

#### Query Parameters
| Parameter         | Type              | Description                                                                                 |
|------------------|-------------------|---------------------------------------------------------------------------------------------|
| timezone         | string            | IANA timezone specifier. If missing, UTC is used. Optional.                                 |
| date             | string (date)     | Will return all entries beginning on a date in the given timezone (YYYY-MM-DD). If `start` or `end` are provided, `date` will be ignored. |
| start            | string (date-time)| Start datetime in modified ISO-8601 format (YYYY-MM-DD or YYYY-MM-DD HH:mm:SS). Timezones/offsets will be ignored; use the query parameter instead. |
| end              | string (date-time)| End datetime in modified ISO-8601 format (YYYY-MM-DD or YYYY-MM-DD HH:mm:SS). Timezones/offsets will be ignored; use the query parameter instead. |
| cursor           | string            | Cursor for pagination to retrieve the next set of lifelogs. Optional.                        |
| direction        | string (enum)     | Sort direction for lifelogs. Allowed values: `asc`, `desc`. Default: `desc`                 |
| includeMarkdown  | boolean           | Whether to include markdown content in the response. Default: `true`                        |
| includeHeadings  | boolean           | Whether to include headings in the response. Default: `true`                                |
| limit            | integer           | Maximum number of lifelogs to return. (Max value is 10; use the cursor parameter for pagination). Default: `3` |

#### Response
Returns a 200 status code with the following response body:

```json
{
  "data": {
    "lifelogs": [
      {
        "id": "string",
        "title": "string",
        "markdown": "string",
        "startTime": "ISO-8601 string",
        "endTime": "ISO-8601 string",
        "contents": [
          {
            "type": "heading1" | "heading2" | "blockquote",
            "content": "string",
            "startTime": "ISO-8601 string",
            "endTime": "ISO-8601 string",
            "startOffsetMs": "timestamp in milliseconds",
            "endOffsetMs": "timestamp in milliseconds",
            "children": [],
            "speakerName": "string",
            "speakerIdentifier": "user" | null
          }
        ]
      }
    ]
  },
  "meta": {
    "lifelogs": {
      "nextCursor": "string",
      "count": 0
    }
  }
}
```

#### Example Request
```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "https://api.limitless.ai/v1/lifelogs?date=2025-03-11&timezone=America/Los_Angeles"
```

#### Example Code (TypeScript)
```typescript
const params = new URLSearchParams({
  date: '2025-03-11',
  timezone: 'America/Los_Angeles'
});
const response = await fetch(`https://api.limitless.ai/v1/lifelogs?${params}` , {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
  },
});
```

#### Example Code (Python)
```python
import requests
response = requests.get(
    'https://api.limitless.ai/v1/lifelogs',
    params={
        'date': '2025-03-11',
        'timezone': 'America/Los_Angeles'
    }, headers={'X-API-Key': 'YOUR_API_KEY'})
```

---

### Get Lifelog
- **GET** `/v1/lifelogs/{lifelog_id}`
- Get a specific Lifelog by ID.

#### Query Parameters
| Parameter         | Type    | Description                                              |
|------------------|---------|----------------------------------------------------------|
| :id              | string  | The ID of the lifelog entry to retrieve, given in the URL.|
| includeMarkdown  | boolean | Whether to include markdown content in the response. Default: `true` |
| includeHeadings  | boolean | Whether to include headings in the response. Default: `true` |

#### Response
Returns a 200 status code with the following response body:

```json
{
  "data": {
    "lifelog": {
      "id": "string",
      "title": "string",
      "markdown": "string",
      "startTime": "ISO-8601 string",
      "endTime": "ISO-8601 string",
      "contents": [
        {
          "type": "heading1" | "heading2" | "blockquote",
          "content": "string",
          "startTime": "ISO-8601 string",
          "endTime": "ISO-8601 string",
          "startOffsetMs": "timestamp in milliseconds",
          "endOffsetMs": "timestamp in milliseconds",
          "children": [],
          "speakerName": "string",
          "speakerIdentifier": "user" | null
        }
      ]
    }
  }
}
```

---

## Authentication
All API requests require authentication using an API key.

Include your API key in the `X-API-Key` header with each request:

```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api.limitless.ai/v1/lifelogs
```

You can obtain an API key from the Developer settings in your Limitless account.

---

## Resources
- [openapi.yml](https://raw.githubusercontent.com/limitless-ai-inc/limitless-api-examples/refs/heads/main/openapi.yml)
- For developers and LLMs

---

## Notes
While the Developer API is in beta, it only supports Pendant data. More endpoints will be added soon.
