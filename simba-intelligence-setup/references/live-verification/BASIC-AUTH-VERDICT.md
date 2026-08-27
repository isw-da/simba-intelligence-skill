# Basic auth on the SI-bundled Composer API: settled

Tested 27 August 2026 against a fresh Simba Intelligence 26.2.1 install (chart pulled from
`oci://docker.io/insightsoftware/simba-intelligence-chart`, Composer present as the subchart
aliased `discovery`), on a local kind cluster.

## The dispute

| Side | Claim | Where |
|---|---|---|
| This knowledge base | "Bundled Symphony usually rejects Basic on the v3 API" | `composer-mcp/README.md:179-180`, `SCHEMA_NOTES.md:13-15` |
| Peter Armstrong | Basic works, with a live `curl --user user:pass` example | `Logi-Composer-Symphony-Embedding-Reference.md:2983`, `:3003` |
| Confluence | Both, scoped differently, Peter right on current behaviour | CMP-4038 open, ZP-28798 closed |

## The result

**Peter is right. Basic auth is accepted.**

```
GET /discovery/api/sources   Accept: application/vnd.composer.v3+json
  valid Basic      HTTP 200   {"content":[]}
  invalid Basic    HTTP 401
  no auth          HTTP 401
```

And the server advertises it unprompted:

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="api"
```

A server that ignored Basic would not challenge with it.

## Why the wrong claim was plausible, which is the useful part

The install generates a 24-character random admin password into the Kubernetes secret
`si-discovery-web`, key `admin.password`. Testing with a guessed credential such as
`admin:admin` returns 401, and the body is an OAuth2 error,
`{"error":"invalid_token","error_description":"Invalid access token"}`, which reads exactly
like "this endpoint wants a bearer token, Basic is not supported".

So the failure mode that produces the wrong belief is: try Basic with a guessed password,
get a bearer-flavoured 401, conclude Basic is rejected. The credential was wrong, not the
mechanism.

## What this verdict does and does not cover

Covers: a default `helm install` of 26.2.1 on kind, `/discovery/api/*`, v3 media type.

Does not cover: Amin's UAT host, where the original observation was made and where
configuration may genuinely differ; and it says nothing about whether Basic is a *good* idea.
CMP-4038 is open specifically to replace Basic on the Symphony-to-Composer hop with a
pre-shared key, so this is current behaviour rather than a durable guarantee.

Also worth recording: `/api/sources` and `/composer/api/sources` return 302 on this
deployment, while `/discovery/api/sources` returns 401 then 200. Getting the context path
wrong produces a redirect that is easy to misread as an auth failure.

## Method note, and a correction to my own work

The first version of the test script reported the exact opposite verdict. Its probe function
printed a label and echoed the status code from the same function, so command substitution
captured both and the comparison compared label text rather than status codes. The second
version reported "Basic is ignored", which was also wrong, because it used a guessed password.
Only the third, using the real credential from the secret and checking the `WWW-Authenticate`
challenge, was sound. Two wrong verdicts before a right one, on a test whose whole purpose was
to be authoritative.
