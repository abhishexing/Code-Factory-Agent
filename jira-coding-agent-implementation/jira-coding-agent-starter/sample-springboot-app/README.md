# Employee Service

Small Spring Boot 3 / Java 21 target repository for the coding-agent POC.
It currently supports POST /employees and GET /employees/{id}, using Spring
Data JPA and an in-memory H2 database.

Deliberately incomplete areas for future Jira tickets:
- Request DTOs and Bean Validation
- Duplicate-email handling
- Centralised exception handling
- List, update and delete endpoints
- Controller/service tests
- Pagination and filtering

Run with Java 21 and Maven: `mvn spring-boot:run` or `mvn test`.
