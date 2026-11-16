# 0002. Licences: MIT for the code, CC BY 4.0 for the reports and results
Date: 2026-11-16
Status: accepted (owner, 2026-11-16: "ok lets do your recommendations")

## Context
The owner wants the project to be open source and its results published on GitHub. Without a licence a public
repository is readable, but nobody may legally reuse it. A licence is hard to take back: copies made under it stay
under it. The repository holds two kinds of work, and software licences fit text poorly:
- program code (so far the day-1 archive; later the agents);
- written work: research reports, decision records, and later the funds' published decisions and results.

Requirements: really open source (the owner's strong preference), simple enough to need no upkeep, and no obstacle for
people who want to reuse the work.

## Options considered

**Code**

| Option | In one sentence | For | Against |
|---|---|---|---|
| **MIT** | Anyone may do anything with it if they keep the copyright line and the licence text. | Very short, the best known, nothing to maintain. | A closed product may be built on it without sharing back. |
| Apache 2.0 | The same freedom, plus formal rules about patents and about marking changes. | Stronger legal footing for companies. | Longer and more formal; its patent rules protect nothing this project has. |
| AGPL 3.0 | Whoever builds on it, even only as a web service, must publish their version under the same licence. | Every derivative stays open. | Many people and most companies avoid AGPL code; it limits which other code can be combined with ours. |

**Reports and results**

| Option | In one sentence |
|---|---|
| **CC BY 4.0** | Reuse and adaptation allowed with credit. |
| CC BY-SA 4.0 | The same, and adaptations must carry the same licence. |
| CC0 | No conditions, not even credit. |

## Decision
- **Code: MIT** (`LICENSE`). Everything under `src/`, `tests/` and `systemd/`, and any other program code.
- **Written work: CC BY 4.0** (`LICENSE-CC-BY-4.0`). Everything under `docs/`, the README, and later the published
  decisions and results.

Why: share-alike licences earn their cost when there is something a company could take and close off. Here the value
is the public experiment and its results, not the code, so being easy to reuse matters more. Creative Commons itself
advises against its licences for software, hence two licences.

## Consequences
- Anyone may reuse the code and the texts, also commercially, with credit.
- The licences cover only our own work. Files from the data sources are not ours, stay outside the repository
  (ADR 0001), and keep their own terms.
- The licences say "no warranty"; the README also says plainly that this is a paper-money experiment and not
  investment advice.
- Most of the code is written by an AI model (Claude) at the owner's direction. Whether such work can carry copyright
  is legally unsettled and differs per country. The licence still states clearly what is allowed.
- Reusing code that has a share-alike licence (GPL, AGPL) inside this project would force that licence onto the
  combined work: check the licence of every dependency and of any copied code first.

## Revisit
Later, maybe: look at the choice again if the project starts to reuse share-alike code, or when other people start
contributing (then decide how their contributions are licensed).

## Sources
- MIT licence: [text and summary](https://choosealicense.com/licenses/mit/), [SPDX](https://spdx.org/licenses/MIT.html)
- Comparison of MIT, Apache 2.0 and AGPL: [choosealicense.com](https://choosealicense.com/licenses/)
- No licence means no permission: [choosealicense.com/no-permission](https://choosealicense.com/no-permission/)
- CC BY 4.0: [summary](https://creativecommons.org/licenses/by/4.0/), [legal text](https://creativecommons.org/licenses/by/4.0/legalcode.txt)
- Creative Commons on software: [FAQ, "Can I apply a Creative Commons license to software?"](https://creativecommons.org/faq/#can-i-apply-a-creative-commons-license-to-software)
- Licensing a repository on GitHub: [GitHub documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
