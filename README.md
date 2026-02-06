# QHub-Wiki
Self-hosted AI powered knowledge base for SMBs: WikiJS + Qdrant Vector search, [Custom QHub Wiki Browser Extension](https://github.com/intelliconnect/QHub-Wiki-BrowserExtension) queries, single Ansible deploy. Unlimited users, no subs - reduce SaaS costs, own your data.

QHub Wiki AI unifies scattered operational knowledge into instant AI answers via Chrome extension. Built by IntelliconnectQ for internal use and their customers as a replacement to  SaaS tool(s).

**Moving content to Markdown is guided by**
1. Optimal LLM compatibility for precise retrieval
2. Industry-standard extensibility (frontmatter, code blocks, diagrams)
3. Future-proof portability across AI platforms

**⚠️ Requires paid LLM API key** (Anthropic Claude, OpenAI, etc.)
with a backup fallback using [GROQ](https://console.groq.com/docs/quickstart)

## 🚀 Choose Your Deployment
### Option 1: Self-Service Ansible

**For teams who prefer Ansible**
See [QHub Wiki Setup using Ansible Scripts](/docs/SETUP_ANSIBLE_INTRO.md)


### Option 2: SemaphoreUI - COMING SOON
About Semaphore UI: Semaphore UI is an open-source web interface designed for managing DevOps automation tools like Ansible, Terraform, OpenTofu, and PowerShell. It offers an intuitive dashboard to run playbooks, scripts, and infrastructure tasks without relying solely on command-line operations.
See [QHub Wiki Setup using SemaphoreUI](/docs/SETUP_SEMAPHORE_UI.md)


## 💾 System Requirements
| Component | Minimum                              | Recommended  |
| --------- | ------------------------------------ | ------------ |
| RAM       | 4 GB                                 | 8 GB         |
| CPU       | 2 cores                              | 4 cores      |
| OS        | Ubuntu 22.04/24.04                   | Ubuntu 24.04 |
| Ports     | 80, 443                              | Same         |
| Disk      | 20 GB                                | 50+ GB       |

**Single-server only** - No Kubernetes/cluster support.

## 💰 Cost Model  
| Component    | Cost          |
|--------------|---------------|
| **Software** |  **FREE**     |
| **LLM API**  | **Your usage**|


## 🏗️ What Gets Deployed
```
┌─────────────────┐      ┌─────────────────┐ 
│ Chrome Ext      │───▶ │ NGINX + API      │ ← Semaphore UI / Ansible
│ (in-browser AI) │      │(SSL Termination │
└─────────────────┘      └─────────────────┘  
                           │
                    ┌──────────────────┐
                    │ WikiJS + Qdrant  │◄── GitHub Sync
                    │ (Docker Compose) │
                    └──────────────────┘
                           │
                    ┌──────────────┐
                    │LLM:Claude etc│
                    └──────────────┘
```



## 📊 Proven Results

* **50% faster onboarding** - New hires self-serve answers
* **$10k+ annual SaaS savings** - Replaces Notion/Confluence

**Verify**: `curl https://wiki.mydomain.com/health`

## 💬 Support

* 🐛 Issues: [GitHub Discussions](https://github.com/intelliconnect/QHub-Wiki/discussions)


**License**: Apache 2.0. See [NOTICE](hhttps://github.com/intelliconnect/QHub-Wiki/docs/NOTICE) for WikiJS (AGPLv3) + Qdrant (Apache 2.0).
