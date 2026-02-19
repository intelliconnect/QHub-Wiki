# 📘 Runbook: Update GROQ/ANTHROPIC LLM API Key (Wiki.js – Doc Embedding API)

## 🎯 Purpose

Update the **GROQ_API_KEY/ANTHROPIC_API_KEY** used by the **doc-embedding-api** service and ensure the new key is correctly loaded by the container.

---

## 📍 Prerequisites

* SSH access to the server
* QHub-Wiki Already setup

---

## 🧭 Step-by-Step Procedure

### 1️⃣ Navigate to Wiki.js application directory

```bash
cd /opt/wiki-js-app
```

---

### 2️⃣ Update the `.env` file

Open the `.env` file using your editor:

```bash
vi .env
```

update the following variable:

```env
GROQ_API_KEY=your_new_groq_api_key_here
ANTHROPIC_API_KEY=your_new_anthropic_api_key_here
```

💡 **Important**

* Do not add quotes unless required
* Ensure there are no extra spaces

Press Esc, then type :wq and press Enter to save and exit.
---

### 3️⃣ Restart only the Doc Embedding API service

Run below Command that Recreate the container so it picks up the updated environment variable:

```bash
docker compose up -d --no-deps --force-recreate doc-embedding-api
```

✅ This ensures:

* Other services are untouched
* Container is recreated
* Latest `.env` values are loaded

---

### 4️⃣ Verify the updated API key inside the container

# For GROQ_API_KEY 

```bash
docker exec -it doc-embedding-api sh -c 'echo $GROQ_API_KEY'
```

# For ANTHROPIC_API_KEY

```bash
docker exec -it doc-embedding-api sh -c 'echo $ANTHROPIC_API_KEY'
```

🔍 Expected result:

* The **new GROQ_API_KEY/ANTHROPIC_API_KEY** should be printed
* If empty or old value → container was not recreated

