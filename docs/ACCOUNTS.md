# Free accounts to create (owner)

Decided 2026-11-16: all free sign-ups are acceptable; the owner creates them. Each service gives a **key** (a long
password for programs). Keys never go into git or into a chat with Claude.

**Where the keys go:** the file `~/projects/bobby-hedgefund/.env` (git ignores it; the nightly backup covers it). Open
it in the text editor, paste each key after its `=` sign, save. The names are already in the file.

**Which address:** any address you like; a second "alias" address in Outlook keeps this mail apart from your normal
inbox. Use a password manager for the passwords.

| # | Service | What it is for | Sign up | Name in `.env` | When |
|---|---|---|---|---|---|
| 1 | **Tiingo** | Daily share prices: the first choice in the research | [tiingo.com](https://www.tiingo.com/), then the key is under "API" in your account ([documentation](https://api.tiingo.com/documentation)) | `TIINGO_API_KEY` | **First.** Needed before the price archive can start |
| 2 | Massive (formerly Polygon) | Second price source; also lists share splits and ticker changes | [massive.com](https://massive.com/pricing), free "Basic" plan | `MASSIVE_API_KEY` | Soon; lets us compare two price sources |
| 3 | openFDA | FDA data with a higher daily limit (120,000 requests instead of 1,000) | [open.fda.gov](https://open.fda.gov/apis/authentication/): e-mail address only, key arrives by mail | `OPENFDA_API_KEY` | When we build the FDA stream |
| 4 | FRED | US interest rates | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | `FRED_API_KEY` | When we build it |
| 5 | NCBI (PubMed) | Paper abstracts, with a higher speed limit | [account.ncbi.nlm.nih.gov](https://account.ncbi.nlm.nih.gov/), then "Account settings", "API Key Management" | `NCBI_API_KEY` | When we build the science stream |
| 6 | AACT | The trial registry as a database, with dated older copies (for the historical study) | [aact.ctti-clinicaltrials.org](https://aact.ctti-clinicaltrials.org/) | `AACT_API_KEY` (the account page offers a key; what it gives access to is not documented publicly, **untested**), `AACT_USER`, `AACT_PASSWORD` (database login, shown after requesting database access) | Before the historical study |
| 7 | FDA Data Dashboard | Factory inspection results | [datadashboard.fda.gov](https://datadashboard.fda.gov/oii/api/index.htm); asks for name and e-mail | `FDA_DASHBOARD_USER`, `FDA_DASHBOARD_KEY` | Later |
| 8 | EPO Open Patent Services | Patent data | [epo.org](https://epo.org/en/searching-for-patents/data/web-services/ops) | `EPO_OPS_KEY`, `EPO_OPS_SECRET` | Later, if patents make it into the spec |
| 9 | OpenAlex | Authors and citations of papers | [help.openalex.org](https://help.openalex.org/api-reference/authentication) | `OPENALEX_API_KEY` | Later |

Also in `.env`, no account needed: `SEC_CONTACT_EMAIL`, the address sent with every request to the SEC (decided
2026-11-16: the owner's normal address is fine).

Status 2026-11-16 (each key tested with one small request, and a made-up key was refused): Tiingo, Massive, openFDA,
FRED, NCBI, FDA Data Dashboard and OpenAlex work. AACT: key saved but untested, database login still refused (the
database username and server address must come from AACT's connection page). EPO: account waiting for approval.
The FDA portal gives one key per service: `FDA_ENFORCEMENT_KEY` is for its Enforcement Reports (recalls) service, untested.
OpenAlex's free key has a daily budget of 1 US dollar of usage (about 10,000 simple requests), no payment details asked.

Not checked: the exact free limits of Tiingo and Massive, and whether each sign-up page still looks as described.
Read each service's terms when you sign up; all were listed as free for personal use in docs/research/DATA-SOURCES.md.
