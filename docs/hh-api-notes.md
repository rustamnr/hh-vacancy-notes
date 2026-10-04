# hh.ru API notes

Source: <https://api.hh.ru/openapi/redoc> (rendered with JavaScript, read it in a browser) and probing with real tokens on 2026-10-04. The API terms change over time; verify before relying on any item here.

## What works for this project

Only the **application token** is useful. Verified with it:

- `GET /vacancies` (search), `GET /vacancies/{id}` (details with `key_skills`, `description`, `response_letter_required`) answer 200.

Verified not to work:

- A user token from the OAuth flow answers 403 `forbidden` on search, `/resumes/mine` and `/negotiations`: hh closed the applicant API (December 2025) and public search requires an application token.
- So there is no reading of resumes, no similar-vacancies for a resume and no automatic applications. Applications are made by hand; the bot gives the letter and the link.

## Requests

- Base URL `https://api.hh.ru/`, HTTPS and JSON only.
- A `User-Agent` or `HH-User-Agent` header is **required**. Format: `MyApp/1.0 (my-app-feedback@example.com)`. Without it the API answers 400.
- The application token never expires. A new one can be requested at most once every 5 minutes, and requesting it revokes the previous one.

## Errors the client tells apart

| Situation | Signal |
|---|---|
| Missing User-Agent | 400, `bad_user_agent` (`unset` / `blacklisted`) |
| Token expired or revoked | 403, `token_expired` / `token_revoked` |
| Captcha | `captcha_required` + `captcha_url` |
| Limits | `limit_exceeded`, `in_a_row_limit`, `overall_limit` |

## Vacancy search

- `GET /vacancies`: `per_page` is at most 100 and the **result depth is capped at 2000** (page * per_page + per_page <= 2000), so broad queries must be split by region and period.
- Filters: `text` (with a query language), `search_field`, `area`, `experience`, `professional_role`, `industry`, `employer_id`, `salary`/`currency`, `label`, `period`, `date_from`.
- The description of a vacancy is one HTML string; there are no separate fields for requirements or responsibilities (only `key_skills` is a list).

## Politeness

The access is a privilege hh can withdraw: the commands pause between requests (500 ms between search pages, 300 ms between vacancy fetches) and stop on captcha or limit errors.
