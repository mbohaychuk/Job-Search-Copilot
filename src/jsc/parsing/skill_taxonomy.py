"""Canonical skill taxonomy with alias mapping.

Maintains a normalized vocabulary of technical skills so that
resume skills and job skills can be compared deterministically.
"""

_TAXONOMY: dict[str, list[str]] = {
    # Languages
    "Python": ["python3", "py"],
    "JavaScript": ["js", "ecmascript", "es6", "es2015"],
    "TypeScript": ["ts"],
    "Java": [],
    "C#": ["csharp", "c sharp", "dotnet", ".net"],
    "C++": ["cpp", "c plus plus"],
    "C": [],
    "Go": ["golang"],
    "Rust": [],
    "Ruby": ["rb"],
    "PHP": [],
    "Swift": [],
    "Kotlin": ["kt"],
    "Scala": [],
    "R": [],
    "Dart": [],
    "Elixir": [],
    "Clojure": [],
    "Haskell": [],
    "Lua": [],
    "Perl": [],
    "Shell": ["bash", "sh", "zsh", "shell scripting"],

    # Frontend
    "React": ["react.js", "reactjs", "react js"],
    "Angular": ["angular.js", "angularjs"],
    "Vue.js": ["vue", "vuejs", "vue.js"],
    "Svelte": ["sveltekit"],
    "Next.js": ["nextjs", "next"],
    "Nuxt.js": ["nuxtjs", "nuxt"],
    "HTML": ["html5"],
    "CSS": ["css3"],
    "Sass": ["scss"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "Bootstrap": [],
    "jQuery": [],
    "Redux": [],
    "Webpack": [],
    "Vite": [],

    # Backend frameworks
    "Django": [],
    "Flask": [],
    "FastAPI": [],
    "Express.js": ["express", "expressjs"],
    "Spring Boot": ["spring", "spring framework"],
    "Rails": ["ruby on rails", "ror"],
    "ASP.NET": ["asp.net core", "aspnet"],
    "NestJS": ["nest.js"],
    "Laravel": [],

    # Databases
    "PostgreSQL": ["postgres", "psql", "pg"],
    "MySQL": ["mariadb"],
    "MongoDB": ["mongo"],
    "Redis": [],
    "Elasticsearch": ["elastic", "es"],
    "SQLite": [],
    "Microsoft SQL Server": ["mssql", "sql server"],
    "Oracle Database": ["oracle db", "oracle"],
    "DynamoDB": ["dynamo"],
    "Cassandra": [],
    "Neo4j": [],
    "SQL": [],

    # Cloud & infrastructure
    "AWS": ["amazon web services"],
    "Azure": ["microsoft azure"],
    "Google Cloud": ["gcp", "google cloud platform"],
    "Docker": [],
    "Kubernetes": ["k8s"],
    "Terraform": [],
    "Ansible": [],
    "Pulumi": [],
    "Helm": [],
    "Nginx": [],
    "Apache": [],

    # CI/CD & DevOps
    "GitHub Actions": ["gh actions"],
    "GitLab CI": ["gitlab ci/cd"],
    "Jenkins": [],
    "CircleCI": [],
    "ArgoCD": ["argo cd"],
    "Git": [],

    # Data & ML
    "Pandas": [],
    "NumPy": ["numpy"],
    "Scikit-learn": ["sklearn"],
    "TensorFlow": ["tf"],
    "PyTorch": ["torch"],
    "Spark": ["apache spark", "pyspark"],
    "Kafka": ["apache kafka"],
    "Airflow": ["apache airflow"],
    "dbt": [],

    # APIs & protocols
    "REST": ["restful", "rest api"],
    "GraphQL": ["gql"],
    "gRPC": [],
    "WebSocket": ["websockets"],
    "OpenAPI": ["swagger"],

    # Testing
    "pytest": [],
    "Jest": [],
    "Cypress": [],
    "Selenium": [],
    "Playwright": [],
    "JUnit": [],
    "Mocha": [],

    # Messaging & queues
    "RabbitMQ": ["rabbit mq"],
    "Celery": [],
    "SQS": ["amazon sqs"],

    # Monitoring & observability
    "Datadog": [],
    "Prometheus": [],
    "Grafana": [],
    "Sentry": [],
    "New Relic": ["newrelic"],

    # Other tools & concepts
    "Linux": [],
    "Agile": ["scrum", "kanban"],
    "Jira": [],
    "Confluence": [],
    "Figma": [],
    "Microservices": ["micro services"],
    "CI/CD": ["cicd", "continuous integration", "continuous delivery"],
    "Machine Learning": ["ml"],
    "Deep Learning": ["dl"],
    "NLP": ["natural language processing"],
    "Computer Vision": ["cv"],
    "OAuth": ["oauth2", "openid connect", "oidc"],
    "JWT": ["json web token"],
    "SSO": ["single sign-on"],
}


class SkillTaxonomy:
    """Maps skill aliases to canonical names for consistent matching."""

    def __init__(self) -> None:
        self._alias_to_canonical: dict[str, str] = {}
        self._canonical_set: set[str] = set()
        self._build_index()

    def _build_index(self) -> None:
        for canonical, aliases in _TAXONOMY.items():
            key = canonical.lower().strip()
            self._canonical_set.add(canonical)
            self._alias_to_canonical[key] = canonical
            for alias in aliases:
                self._alias_to_canonical[alias.lower().strip()] = canonical

    def canonicalize(self, skill: str) -> str | None:
        """Map a skill string to its canonical form, or None if unknown."""
        return self._alias_to_canonical.get(skill.lower().strip())

    def canonicalize_or_keep(self, skill: str) -> str:
        """Map to canonical form, or return the original if unknown."""
        return self._alias_to_canonical.get(skill.lower().strip(), skill.strip())

    def is_known(self, skill: str) -> bool:
        return skill.lower().strip() in self._alias_to_canonical

    @property
    def all_canonical(self) -> set[str]:
        return self._canonical_set.copy()

    def find_skills_in_text(self, text: str) -> list[str]:
        """Find known skills mentioned in text via keyword matching.

        Returns canonical skill names found.
        """
        text_lower = text.lower()
        found: set[str] = set()
        for alias, canonical in self._alias_to_canonical.items():
            # Require word boundaries to avoid false positives (e.g. "Go" in "good")
            if len(alias) <= 2:
                # Short aliases need stricter matching
                import re
                if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                    found.add(canonical)
            else:
                if alias in text_lower:
                    found.add(canonical)
        return sorted(found)
