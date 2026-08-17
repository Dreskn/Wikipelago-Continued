"""Build the EN union Grand Goal review markdown (no lead excerpts)."""
from __future__ import annotations

import json
from pathlib import Path

from _build_review_md import QUESTIONS

HERE = Path(__file__).resolve().parent
OLD_SRC = HERE / "questions-en-top100-source.json"
SRC = HERE / "questions-en-union-source.json"
OUT = HERE / "questions-en-union.md"

EXTRA: dict[str, dict[str, str]] = {
    "AMGTV": {
        "question": "Which American digital multicast network uses the letters AMG and is aimed at family-oriented over-the-air viewers?",
        "fact": "No Wikipedia lead was returned; clue is a placeholder — check or reject.",
    },
    "Earth": {
        "question": "Which planet is third from the Sun and the only astronomical object known to harbor life?",
        "fact": "Third planet; only known world with life; ocean covers 70.8% of the crust.",
    },
    "Millennials": {
        "question": "Which generation is typically defined as people born from 1981 to 1996, between Generation X and Generation Z?",
        "fact": "Gen Y; usual birth years 1981–1996.",
    },
    "2022 Russian invasion of Ukraine": {
        "question": "Which invasion, launched on 24 February 2022, became Europe's largest conflict since World War II after a rapid northern victory failed?",
        "fact": "Full-scale invasion 24 Feb 2022; largest European war since WWII.",
    },
    "Vietnam War": {
        "question": "Which conflict in Vietnam, Laos, and Cambodia ended on 30 April 1975 after U.S. forces had withdrawn two years earlier?",
        "fact": "c. 1955–30 April 1975; U.S. withdrawal 1973.",
    },
    "Soviet Union": {
        "question": "Which transcontinental state, formed in 1922 and dissolved in 1991, was the world's largest country by area and third-most populous?",
        "fact": "USSR 1922–1991; largest by area, third-most populous. Not the capital.",
    },
    "Netflix": {
        "question": "Which service launched streaming in 2007, nearly a decade after its DVD-by-mail rental business, and later became the most-subscribed global video-on-demand platform?",
        "fact": "Streaming launch 2007 after DVD-by-mail; most-subscribed VOD service.",
    },
    "HTTP 404": {
        "question": "Which HTTP status code means a client reached the server but the requested resource could not be provided, often shown as 'Not Found'?",
        "fact": "404; Not Found / page not found.",
    },
    "William Shakespeare": {
        "question": "Which English playwright, often called the Bard of Avon, left about 39 plays and 154 sonnets?",
        "fact": "Bard of Avon; ~39 plays, 154 sonnets.",
    },
    "American Civil War": {
        "question": "Which U.S. war, fought from 1861 to 1865 between the Union and the Confederacy, ended with the abolition of slavery?",
        "fact": "12 Apr 1861 – 26 May 1865; Union vs Confederacy; slavery abolished.",
    },
    "Seven deadly sins": {
        "question": "Which grouping of Christian vices, in the Catholic list, comprises pride, envy, wrath, gluttony, lust, sloth, and greed?",
        "fact": "Catholic seven: pride, envy, wrath, gluttony, lust, sloth, greed.",
    },
    "Generation Z": {
        "question": "Which generation is typically defined as people born from 1997 to 2012, after Millennials and before Generation Alpha?",
        "fact": "Zoomers; usual birth years 1997–2012.",
    },
    "Sexual intercourse": {
        "question": "Which intimate activity is more formally called coitus or copulation and typically involves vaginal penetration?",
        "fact": "Formal names coitus/copulation. Likely reject as a Grand Goal.",
    },
    "Jesus": {
        "question": "Which 1st-century Jewish preacher from the Roman province of Judaea is the central figure of Christianity?",
        "fact": "1st-century preacher in Judaea; central figure of Christianity.",
    },
    "Harry Potter": {
        "question": "Which seven-book children's fantasy series by J. K. Rowling follows a young wizard and his friends at Hogwarts?",
        "fact": "Seven novels; Hogwarts; Harry, Ron, Hermione vs Voldemort.",
    },
    "J. Robert Oppenheimer": {
        "question": "Which American physicist directed the Manhattan Project's Los Alamos Laboratory and is often called the father of the atomic bomb?",
        "fact": "Los Alamos director; 'father of the atomic bomb'.",
    },
    "Twitter": {
        "question": "Which microblogging service, launched in 2006 by Jack Dorsey and co-founders, was later rebranded as X?",
        "fact": "Created March 2006; later renamed X.",
    },
    "Apple Inc.": {
        "question": "Which Cupertino company was founded in 1976 by Steve Jobs, Steve Wozniak, and Ronald Wayne to market the Apple I?",
        "fact": "Founded 1976; Apple I; Jobs, Wozniak, Wayne.",
    },
    "Skathi (moon)": {
        "question": "Which irregular moon of Saturn, also called Saturn XXVII, was discovered in 2000 and named after the Norse figure Skaði?",
        "fact": "Saturn XXVII; discovered 23 Sep 2000; named for Skaði.",
    },
    "Coronavirus": {
        "question": "Which group of RNA viruses includes the pathogens behind SARS, MERS, and COVID-19?",
        "fact": "Orthocoronavirinae; SARS, MERS, COVID-19.",
    },
    "COVID-19 pandemic": {
        "question": "Which pandemic began with an outbreak in Wuhan in December 2019 and was declared a pandemic by the WHO on 11 March 2020?",
        "fact": "Wuhan Dec 2019; WHO pandemic declaration 11 Mar 2020.",
    },
    "Cat": {
        "question": "Which small domesticated carnivore, Felis catus, is an obligate meat-eater with retractable claws?",
        "fact": "Felis catus; obligate carnivore; retractable claws.",
    },
    "Limonene": {
        "question": "Which cyclic monoterpene is the main fragrant component of citrus fruit peels and takes its name from the Italian for lemon?",
        "fact": "Major component of citrus peel oil; name from limone.",
    },
    "Nikola Tesla": {
        "question": "Which Serbian-American inventor is known for designing the modern alternating-current electricity supply system after emigrating to the United States in 1884?",
        "fact": "AC power system; emigrated 1884.",
    },
    "Wordle": {
        "question": "Which daily web game, created by Josh Wardle, gives players six tries to guess a shared five-letter word?",
        "fact": "Josh Wardle; six guesses; one shared daily five-letter word.",
    },
    "Raindrop cake": {
        "question": "Which Japanese confection made of water and agar is shaped like a large raindrop and became popular in 2014?",
        "fact": "Wagashi of water + agar; popular in Japan in 2014.",
    },
    "Spanish flu": {
        "question": "Which influenza pandemic, caused by H1N1, began around 1918 and is estimated to have killed at least 17 million people?",
        "fact": "1918–1920 H1N1 pandemic; 17–50 million deaths.",
    },
    "Gordon Ramsay": {
        "question": "Which British chef's Chelsea restaurant has held three Michelin stars since 2001?",
        "fact": "Restaurant Gordon Ramsay, Chelsea; three stars since 2001.",
    },
    "Halloween": {
        "question": "Which 31 October observance is also called All Hallows' Eve and sits on the night before All Saints' Day?",
        "fact": "31 October; All Hallows' Eve / All Saints' Eve.",
    },
    "Minecraft": {
        "question": "Which sandbox game, developed by Mojang, had a public alpha in 2009 and a full PC release in November 2011?",
        "fact": "Mojang; public alpha 2009; release November 2011.",
    },
    "Roblox": {
        "question": "Which game platform, created by David Baszucki and Erik Cassel, launched publicly in 2006 and uses the virtual currency Robux?",
        "fact": "Baszucki and Cassel; public 2006; Robux.",
    },
    "Steven Spielberg": {
        "question": "Which American director is the highest-grossing filmmaker of all time and a pioneer of the modern blockbuster?",
        "fact": "Highest-grossing director; modern blockbuster pioneer.",
    },
    "Nelson Mandela": {
        "question": "Which anti-apartheid leader became South Africa's first Black president after the country's first fully representative election, serving from 1994 to 1999?",
        "fact": "President 1994–1999; first Black head of state.",
    },
    "Anthony Bourdain": {
        "question": "Which chef's 2000 book Kitchen Confidential followed a New Yorker essay and years as executive chef at Brasserie Les Halles?",
        "fact": "Kitchen Confidential (2000); Les Halles; New Yorker essay.",
    },
    "IOS": {
        "question": "Which mobile OS was unveiled in January 2007 alongside the first iPhone and released that June?",
        "fact": "Unveiled Jan 2007 with iPhone; released June 2007.",
    },
    "MacOS": {
        "question": "Which Apple desktop OS succeeded classic Mac OS after the company acquired NeXT and based the system on NeXTSTEP?",
        "fact": "Succeeded classic Mac OS; architecture from NeXT/NeXTSTEP.",
    },
    "Coca-Cola": {
        "question": "Which soft drink was invented in Atlanta by John Stith Pemberton and later sold to Asa Candler in 1888?",
        "fact": "Pemberton, Atlanta; rights sold to Candler 1888.",
    },
    "Brownie (folklore)": {
        "question": "Which Scottish household spirit is said to do chores at night if left a bowl of milk by the hearth, and to leave forever if insulted?",
        "fact": "Scottish hobgoblin; milk by the hearth; easily offended.",
    },
    "Thanksgiving": {
        "question": "Which harvest holiday is a national observance in the United States, Canada, Saint Lucia, and Liberia, though on different dates?",
        "fact": "National holiday in those four countries; harvest thanks.",
    },
    "Attack on Titan": {
        "question": "Which manga by Hajime Isayama, serialized from 2009 to 2021, is set behind walls that keep out man-eating Titans?",
        "fact": "Isayama; Bessatsu Shōnen 2009–2021; Titans and walls.",
    },
    "2026 Iran war": {
        "question": "Which 2026 war began after U.S.–Israeli airstrikes killed Iranian officials, including Supreme Leader Ali Khamenei?",
        "fact": "Hostilities from 28 Feb 2026. Current-events page — likely reject.",
    },
    "Demon Slayer: Kimetsu no Yaiba": {
        "question": "Which manga by Koyoharu Gotouge follows Tanjiro Kamado after his family is slaughtered and his sister Nezuko is turned into a demon?",
        "fact": "Gotouge; WSJ 2016–2020; Tanjiro and Nezuko.",
    },
    "Asperger syndrome": {
        "question": "Which former diagnosis, marked by social-interaction difficulties and restricted interests, was merged into autism spectrum disorder in the DSM-5 in 2013?",
        "fact": "Merged into ASD in DSM-5 (2013) and ICD-11 (2022).",
    },
    "Jujutsu Kaisen": {
        "question": "Which manga by Gege Akutami follows Yuji Itadori after he becomes the host of the curse Ryomen Sukuna?",
        "fact": "Akutami; Yuji Itadori hosts Sukuna.",
    },
    "My Hero Academia": {
        "question": "Which manga by Kōhei Horikoshi is set in a world of Quirks and follows a quirkless boy who inherits power from All Might?",
        "fact": "Horikoshi; Quirks; Midoriya inherits All Might's power.",
    },
    "BDSM": {
        "question": "Which catch-all term for bondage, discipline, dominance, submission, and sadomasochism was first recorded on Usenet in 1991?",
        "fact": "Usenet 1991 initialism. Likely reject as a Grand Goal.",
    },
    "Santa Claus": {
        "question": "Which legendary gift-bringer of Western Christian culture is based on a 4th-century Greek bishop who was patron saint of children?",
        "fact": "Derived from Saint Nicholas, 4th-century bishop.",
    },
    "Krampus": {
        "question": "Which horned Alpine figure is said to accompany Saint Nicholas on 5 December and punish badly behaved children with birch rods?",
        "fact": "Krampusnacht, 5 December; birch rods.",
    },
    "Animal": {
        "question": "Which biological kingdom consists of multicellular eukaryotes that grow from a blastula and includes more than 1.5 million described living species?",
        "fact": "Kingdom Animalia; blastula; >1.5 million described species.",
    },
    "Alita: Battle Angel": {
        "question": "Which 2019 cyberpunk film, directed by Robert Rodriguez and produced by James Cameron, adapts Yukito Kishiro's manga Gunnm?",
        "fact": "Rodriguez / Cameron; 2019; based on Gunnm.",
    },
    "COVID-19": {
        "question": "Which contagious disease, caused by SARS-CoV-2, spread worldwide from January 2020 and led to a pandemic?",
        "fact": "Disease caused by SARS-CoV-2; pandemic from 2020.",
    },
    "Ragnar Lodbrok": {
        "question": "Which legendary Viking, nicknamed 'hairy-breeches,' is said to have raided the British Isles and the Carolingian Empire in the 9th century?",
        "fact": "Old Norse loðbrók; 9th-century raids.",
    },
    "Lyme disease": {
        "question": "Which tick-borne illness, caused by Borrelia and spread by Ixodes ticks, often begins with an expanding red rash called erythema migrans?",
        "fact": "Borrelia; Ixodes; erythema migrans.",
    },
    "Bermuda Triangle": {
        "question": "Which loosely defined North Atlantic region, bounded roughly by Florida, Bermuda, and Puerto Rico, is the subject of a disappearance urban legend?",
        "fact": "Florida–Bermuda–Puerto Rico; urban legend, no unusual evidence.",
    },
    "COVID-19 vaccine": {
        "question": "Which class of vaccine, with first clinical trials in March 2020, was developed at unprecedented speed against SARS-CoV-2?",
        "fact": "First trials March 2020; mRNA and other platforms.",
    },
    "Ray Kroc": {
        "question": "Which salesman bought the McDonald's brand from the McDonald brothers in 1961 after years as their franchising agent?",
        "fact": "Purchased the brand in 1961 after franchising.",
    },
    "Strawberry": {
        "question": "Which fruit, botanically an aggregate accessory fruit rather than a berry, was first bred in Brittany in the 1750s?",
        "fact": "Fragaria × ananassa; not a berry; Brittany, 1750s.",
    },
    "Dog": {
        "question": "Which animal, a domesticated descendant of wolves, was the first species humans domesticated, over 14,000 years ago?",
        "fact": "First domesticated species; from wolves; >14,000 years.",
    },
    "The Great British Bake Off": {
        "question": "Which British baking contest, produced by Love Productions, first aired on 17 August 2010 and eliminates one amateur baker each round?",
        "fact": "Love Productions; debut 17 Aug 2010; one elimination per round.",
    },
    "Alice in Borderland (TV series)": {
        "question": "Which Japanese series, based on Haro Aso's manga, strands allies in an empty Tokyo where they must win deadly games to extend their visas?",
        "fact": "Shinsuke Sato; empty Tokyo; visa games.",
    },
    "McDonald's": {
        "question": "Which fast-food chain began as a 1940 San Bernardino restaurant and introduced the Golden Arches design in 1953?",
        "fact": "1940 San Bernardino; Golden Arches 1953.",
    },
    "One Piece": {
        "question": "Which manga by Eiichiro Oda, serialized since July 1997, follows Monkey D. Luffy's search for a legendary treasure to become King of the Pirates?",
        "fact": "Oda; Weekly Shōnen Jump since July 1997; Luffy / One Piece treasure.",
    },
    "Santa Claus's reindeer": {
        "question": "Which festive team of eight, named in the 1823 poem A Visit from St. Nicholas, is later often joined by a red-nosed ninth?",
        "fact": "Eight in 1823 poem; Rudolph added later.",
    },
    "Attack on Titan (TV series)": {
        "question": "Which anime, based on Hajime Isayama's manga, premiered on 7 April 2013 and concluded on 5 November 2023?",
        "fact": "7 Apr 2013 – 5 Nov 2023; Wit then MAPPA.",
    },
    "The Backrooms": {
        "question": "Which creepypasta setting, invented in a 2019 4chan thread, is an endless complex of empty yellow rooms reached by 'exiting reality'?",
        "fact": "2019 4chan; liminal yellow rooms.",
    },
    "Dragon Ball Super": {
        "question": "Which Dragon Ball manga, written by Akira Toriyama and drawn by Toyotarou, began in V Jump in June 2015 during the timeskip after Majin Boo's defeat?",
        "fact": "Toriyama / Toyotarou; V Jump June 2015; post-Boo timeskip.",
    },
    "Demon Slayer: Kimetsu no Yaiba – The Movie: Infinity Castle": {
        "question": "Which 2025 Demon Slayer film, directed by Haruo Sotozaki, adapts the Infinity Castle arc as a sequel to the anime's fourth season?",
        "fact": "2025; Sotozaki / Ufotable; Infinity Castle arc.",
    },
    "Annabelle (doll)": {
        "question": "Which Raggedy Ann doll did paranormal investigators Ed and Lorraine Warren claim was haunted and later moved to their Connecticut museum?",
        "fact": "Raggedy Ann; Warrens; Connecticut museum.",
    },
    "Algae": {
        "question": "Which diverse group of photosynthetic organisms excludes land plants and ranges from microscopic phytoplankton to 50-metre seaweeds?",
        "fact": "Photosynthetic; excludes embryophytes; micro to 50 m macroalgae.",
    },
    "Anglerfish": {
        "question": "Which order of ray-finned fish hunts with a modified dorsal-fin ray that acts as a lure, with the tip called the esca?",
        "fact": "Lophiiformes; esca/illicium lure.",
    },
    "Artichoke": {
        "question": "Which thistle variety is eaten for its flower buds before they bloom, on an edible base of bracts?",
        "fact": "Cynara cardunculus var. scolymus; edible unopened flower head.",
    },
    "Beast of Gévaudan": {
        "question": "Which man-eating animal, or animals, terrorized south-central France between 1764 and 1767 in the former province of Gévaudan?",
        "fact": "1764–1767; Gévaudan / Lozère.",
    },
    "Black cat": {
        "question": "Which coat colour in domestic cats is often linked to witch folklore, and is the only colour of the Bombay breed?",
        "fact": "Solid black; Bombay is exclusively black; witch folklore.",
    },
}

HEADER = """# Grand Goal questions — English union (draft)

Hand-check this list. Nothing here is wired into the game yet.

## How these were picked

Union of:

1. **Top 100** usable English pool pages by all-time visits (`pageviews_aggregate_en.json` `top_by_sum`).
2. **Top 10** usable pages **in each pool tag**.

Same filters as the earlier top-100 list: in `pool_en.json`, not sensitive, no lists/portals/Wikipedia-namespace, no obvious junk.

**173 pages** = 100 overall + 73 that only appear because they are top 10 in a thinner category (anime, food, animals, biology, mythology, etc.).

**Via** on each item is why it was included (`overall` and/or tag names).

## Rules used when writing

- Closed question: exactly one intended Wikipedia page.
- Do not name the answer in the question.
- If the page is a **country**, do not ask for its capital.
- If the page is a **person**, do not ask for their birthplace as the answer (birthplace may appear as a clue).
- Prefer a distinctive lead fact over the most famous one-line identity.
- Still not a riddle and not an open essay.

## How to mark

For each item, tick **one**:

- `[x] accept`
- `[x] edit` — rewrite the question in **Notes**
- `[x] reject` — page or clue is a bad Grand Goal

Worth a hard look: xXx movies, Epstein, Hitler, Escobar, current-events pages (`2026 Iran war`), and a few biology/misc pages (`Sexual intercourse`, `BDSM`, `HTTP 404`, `AMGTV`).

---
"""


def wiki_link(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")


def main() -> None:
    old_src = json.loads(OLD_SRC.read_text(encoding="utf-8"))
    by_old_title = {
        entry["title"]: QUESTIONS[index]
        for index, entry in enumerate(old_src["entries"])
    }
    data = json.loads(SRC.read_text(encoding="utf-8"))
    missing = [e["title"] for e in data["entries"] if e["title"] not in by_old_title and e["title"] not in EXTRA]
    if missing:
        raise SystemExit("Missing questions for: " + "; ".join(missing))

    per_tag = data.get("per_tag_top10") or {}
    tag_lines = ["## Category top 10 (for jumping)\n"]
    for tag, titles in per_tag.items():
        joined = ", ".join(titles)
        tag_lines.append(f"- **{tag}:** {joined}")
    tag_lines.append("")

    chunks = [HEADER, "\n".join(tag_lines), "---\n"]
    for index, src in enumerate(data["entries"], start=1):
        title = src["title"]
        q = by_old_title.get(title) or EXTRA[title]
        tags = ", ".join(src.get("tags") or [])
        via = ", ".join(src.get("via") or [])
        views = src.get("views_summed_from_monthly_tops") or 0
        chunks.append(
            f"## {index:03d}. {title}\n\n"
            f"- **Answer page:** [{title}]({wiki_link(title)})\n"
            f"- **Tags:** {tags}\n"
            f"- **Via:** {via}\n"
            f"- **Pageviews sum (monthly tops):** {views:,}\n"
            f"- **Question:** {q['question']}\n"
            f"- **Lead fact used:** {q['fact']}\n"
            f"- **Validate:** [ ] accept &nbsp; [ ] edit &nbsp; [ ] reject\n"
            f"- **Notes:**\n"
        )
    OUT.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(data['entries'])} items)")


if __name__ == "__main__":
    main()
