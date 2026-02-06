
[← Previous: Pre-requisites](SETUP_ANSIBLE_INTRO.md) | [Next: GitHub Config →](GITHUB_CONFIG.md)

## Setup DNS Configuration

Add 3 A records as below:

| Record Type | DNS Name                    | IP Address    |
| ----------- | --------------------------- | ------------- |
| A           | wiki                        | VM Public IP  |
| A           | qdrant                      | VM Public IP  |
| A           | docs-embeddings-qdrant      | VM Public IP  |

**Note**: You can select your own subdomain for wiki (like `wikijs`, `wiki`, `docs` etc).

![A Record for Wiki](images/dns-img/001-ARecord-wiki.png)

**Mandatory**: Use `qdrant` as the subdomain  
![A Record for qdrant](images/dns-img/002-ARecord-qdrant.png)

**Mandatory**: Use `docs-embeddings-qdrant` as the subdomain  
![A Record for docs-embeddings-qdrant](images/dns-img/003-ARecord-docs-embeddings-qdrant.png)


[← Previous: Pre-requisites](SETUP_ANSIBLE.md) | [Next: GitHub Config →](GITHUB_CONFIG.md)