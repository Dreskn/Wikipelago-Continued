"""Build the EN top-100 Grand Goal review markdown from fetched leads + hand questions."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "questions-en-top100-source.json"
OUT = HERE / "questions-en-top100.md"

# One closed question per ranked title. Index 0 = rank 1.
QUESTIONS: list[dict[str, str]] = [
    {
        "question": "Which house of the U.S. Congress has exclusive power to try impeachment cases brought by the other chamber, and seats two members from each state?",
        "fact": "Upper house; tries impeachments; two senators per state.",
    },
    {
        "question": "Which U.S. president hosted the reality series The Apprentice from 2004 to 2015 between careers in real estate and elective office?",
        "fact": "Hosted The Apprentice 2004–2015; later 45th and 47th president.",
    },
    {
        "question": "After which Hellenistic queen's death in 30 BC did Egypt become a Roman province, ending the Hellenistic period in the Mediterranean?",
        "fact": "Last active Hellenistic pharaoh; death marks Egypt as a Roman province.",
    },
    {
        "question": "Which video site, started by three former PayPal employees, was already uploading more than 500 hours of video every minute by 2019?",
        "fact": "Founded by Hurley, Karim, and Chen; 500+ hours uploaded per minute by 2019.",
    },
    {
        "question": "Which British queen became heir presumptive at age ten after her uncle abdicated in 1936?",
        "fact": "Edward VIII's abdication made ten-year-old Princess Elizabeth heir presumptive.",
    },
    {
        "question": "Which businessman co-founded the web firm Zip2 in 1995 and later X.com, which merged into PayPal?",
        "fact": "Zip2 (1995) then X.com → PayPal; not Tesla/SpaceX as the hook.",
    },
    {
        "question": "Which encyclopedia has been hosted since 2003 by a U.S. nonprofit funded mainly by donations from readers?",
        "fact": "Hosted by the Wikimedia Foundation since 2003; donation-funded.",
    },
    {
        "question": "Which federal republic began with the 1607 Virginia settlement that grew into the Thirteen Colonies, and today includes Alaska as a semi-exclave?",
        "fact": "1607 Virginia / Thirteen Colonies; Alaska semi-exclave. Not the capital.",
    },
    {
        "question": "Which Portuguese forward holds the UEFA Champions League records for most goals (140) and assists (42)?",
        "fact": "Champions League goals 140 and assists 42.",
    },
    {
        "question": "Which anthology of scriptures includes a Hebrew collection whose three parts are remembered by the acronym Tanakh?",
        "fact": "Hebrew Bible = Torah, Nevi'im, Ketuvim → Tanakh.",
    },
    {
        "question": "Which chatbot reached 100 million monthly users within two months of a 30 November 2022 launch?",
        "fact": "Released 30 Nov 2022; 100 million MAU in two months.",
    },
    {
        "question": "Which social network was first limited to Harvard students and takes its name from campus photo directories?",
        "fact": "Harvard-only launch; name from 'face book' directories.",
    },
    {
        "question": "Which Florida-born rapper is often credited with helping establish emo rap and SoundCloud rap before his death in 2018?",
        "fact": "Emo rap / SoundCloud rap figure; died 2018.",
    },
    {
        "question": "Which South Asian country is the world's largest by population and seventh-largest by area, with coasts on the Arabian Sea and the Bay of Bengal?",
        "fact": "Largest population, 7th by area; Arabian Sea and Bay of Bengal. Not the capital.",
    },
    {
        "question": "Which Argentine forward scored 672 club goals for Barcelona, a record for a single club?",
        "fact": "672 goals for Barcelona, most for one club.",
    },
    {
        "question": "Which U.S. president represented Delaware in the Senate from 1973 to 2009 before serving as vice president under Obama?",
        "fact": "Delaware senator 1973–2009; 47th vice president.",
    },
    {
        "question": "Which company, founded by Larry Page and Sergey Brin in 1998, became a wholly owned subsidiary of Alphabet in 2015?",
        "fact": "Founded 1998; Alphabet reorganization 2015.",
    },
    {
        "question": "Which photo app, later owned by Meta, was originally distinguished by requiring posts to be framed as squares?",
        "fact": "Originally square-only framing; later a Meta platform.",
    },
    {
        "question": "Which Queen singer was born Farrokh Bulsara in Zanzibar to Parsi Indian parents and later fled the 1964 revolution?",
        "fact": "Birth name Farrokh Bulsara; Parsi parents; 1964 Zanzibar Revolution. Answer is the person, not the place.",
    },
    {
        "question": "Which 1939–1945 war's aftermath included occupation of Germany, Austria, Japan, and Korea plus trials of German and Japanese leaders?",
        "fact": "Postwar occupation of those four; war-crimes trials.",
    },
    {
        "question": "Which singer signed with Big Machine Records in 2005 and later marked a shift from country to synth-pop with the album 1989?",
        "fact": "Big Machine 2005; 1989 (2014) as the pop turn.",
    },
    {
        "question": "Which American action-spy franchise created by Rich Wilkes consists of three features about Xander Cage, starting in 2002?",
        "fact": "Created by Rich Wilkes; three films, Xander Cage.",
    },
    {
        "question": "Which California attorney general and senator became the first woman, first African American, and first Asian American U.S. vice president?",
        "fact": "First female, African American, and Asian American VP.",
    },
    {
        "question": "Which future U.S. president was the first Black president of the Harvard Law Review?",
        "fact": "First Black president of the Harvard Law Review.",
    },
    {
        "question": "Which singer, the eighth of ten siblings, released Thriller, later called the best-selling album in history?",
        "fact": "Eighth of ten Jackson children; Thriller best-selling album.",
    },
    {
        "question": "Which British queen was granted the extra title Empress of India by parliament in 1876?",
        "fact": "Empress of India from 1876.",
    },
    {
        "question": "Which country comprises England, Scotland, Wales, and Northern Ireland and shares a land border only with the Republic of Ireland?",
        "fact": "Four constituent countries; only land border is with Ireland. Not London.",
    },
    {
        "question": "Which actor won a football scholarship as a Miami defensive tackle before becoming a WWF star during the Attitude Era?",
        "fact": "University of Miami DT; Attitude Era wrestling.",
    },
    {
        "question": "Which Nazi leader took the title Führer und Reichskanzler in 1934 after becoming German chancellor the year before?",
        "fact": "Chancellor 1933; Führer und Reichskanzler 1934.",
    },
    {
        "question": "Which Canadian actor, born in Beirut and raised in Toronto, broke through in Bill & Ted's Excellent Adventure?",
        "fact": "Born Beirut, raised Toronto; Bill & Ted breakthrough.",
    },
    {
        "question": "Which NBA player made eight consecutive Finals from 2011 to 2018 and later became the league's all-time leading scorer?",
        "fact": "Eight straight Finals 2011–2018; NBA all-time scoring leader.",
    },
    {
        "question": "Which 2002 spy film from the director and producer of The Fast and the Furious stars Vin Diesel as extreme-sports rebel Xander Cage?",
        "fact": "Rob Cohen / Neal Moritz / Vin Diesel team from Fast and the Furious.",
    },
    {
        "question": "Which player was taken third in the 1984 NBA draft after winning an NCAA title as a North Carolina freshman in 1982?",
        "fact": "1982 UNC freshman title; 3rd pick in 1984.",
    },
    {
        "question": "Which 2017 Vin Diesel sequel, directed by D. J. Caruso, became the highest-grossing film in the xXx series?",
        "fact": "D. J. Caruso, 2017; franchise's highest grosser.",
    },
    {
        "question": "Which singer began recording at Sun Records in 1954 after his family moved from Tupelo to Memphis?",
        "fact": "Sun Records 1954; Tupelo then Memphis. Answer is the person.",
    },
    {
        "question": "Which financier began his career as a math teacher at New York's Dalton School before later facing sex-trafficking charges?",
        "fact": "Dalton School math teacher, then finance. Page may be rejected in review.",
    },
    {
        "question": "Which singer first became widely known as Cat Valentine on Nickelodeon's Victorious after appearing in the Broadway musical 13?",
        "fact": "Broadway 13 (2008); Cat Valentine on Victorious.",
    },
    {
        "question": "Which actor received both an Honorary Palme d'Or and an Academy Honorary Award after breakthroughs in Risky Business and Top Gun?",
        "fact": "Honorary Palme d'Or and Academy Honorary Award; those two films.",
    },
    {
        "question": "Which royal, born a prince of Greece and Denmark, was the longest-serving consort in British history?",
        "fact": "Born Prince of Greece and Denmark; longest-serving British consort.",
    },
    {
        "question": "Which king was the last Emperor of India, a title that ended when the British Raj was dissolved in 1947?",
        "fact": "Last Emperor of India until August 1947.",
    },
    {
        "question": "Which 1914–1918 war between the Allies and the Central Powers is also linked to spreading the Spanish flu pandemic?",
        "fact": "Allies vs Central Powers; helped spread Spanish flu.",
    },
    {
        "question": "Which Russian leader resigned from the KGB as a lieutenant colonel in 1991 and later briefly directed the FSB before becoming prime minister?",
        "fact": "KGB lt. colonel until 1991; FSB director, then PM in 1999.",
    },
    {
        "question": "Which HBO series adapted George R. R. Martin's novels into 73 episodes across eight seasons, ending in 2019?",
        "fact": "73 episodes, eight seasons, 2011–2019.",
    },
    {
        "question": "Which Star Wars villain first appeared in a 1976 novelization the year before the original film, later becoming a cyborg after a duel with Obi-Wan Kenobi?",
        "fact": "1976 novelization before 1977 film; cyborg after Obi-Wan duel.",
    },
    {
        "question": "Which actress won a BAFTA for Lost in Translation and later became the second-highest-grossing actor in history?",
        "fact": "BAFTA for Lost in Translation; second-highest-grossing actor.",
    },
    {
        "question": "Which younger daughter of George VI remained at Windsor Castle during the Second World War instead of being evacuated to Canada?",
        "fact": "Stayed at Windsor in WWII; only sibling of Elizabeth II.",
    },
    {
        "question": "Which royal was working as a nursery teacher's assistant when she became engaged to the Prince of Wales in 1981?",
        "fact": "Nursery assistant at engagement; married at St Paul's, July 1981.",
    },
    {
        "question": "Which American photographer helped found Group f/64 and, with Fred Archer, developed the Zone System?",
        "fact": "Group f/64; Zone System with Fred Archer.",
    },
    {
        "question": "Which singer first drew notice in 2015 with 'Ocean Eyes,' written and produced by her brother Finneas and posted to SoundCloud?",
        "fact": "Ocean Eyes, 2015, SoundCloud, brother Finneas.",
    },
    {
        "question": "Which Netflix series, created by the Duffer Brothers, is set in 1980s Hawkins, Indiana, after a girl nicknamed Eleven opens a gate to the Upside Down?",
        "fact": "Hawkins, Eleven, Upside Down; Duffer Brothers.",
    },
    {
        "question": "Which English football league was founded on 20 February 1992 when First Division clubs broke away from the Football League?",
        "fact": "FA Premier League founded 20 Feb 1992 as a breakaway.",
    },
    {
        "question": "Which actor made his film debut in A Nightmare on Elm Street (1984) before becoming a teen idol on 21 Jump Street?",
        "fact": "Elm Street 1984; 21 Jump Street 1987–1990.",
    },
    {
        "question": "Which East Asian country is divided into 33 province-level units, including two special administrative regions, and was first unified under the Qin in 221 BCE?",
        "fact": "33 province-level divisions + 2 SARs; Qin unification 221 BCE. Not the capital.",
    },
    {
        "question": "Which Indian T20 cricket league, founded in 2007, became the first sporting event to broadcast live on YouTube in 2010?",
        "fact": "Founded 2007; first live sport on YouTube, 2010.",
    },
    {
        "question": "Which quarterback, selected 199th overall in 2000, spent his first 20 NFL seasons with the New England Patriots?",
        "fact": "199th pick, 2000; 20 seasons with Patriots.",
    },
    {
        "question": "Which U.S. president, a former PT-boat commander, was the youngest person elected to the office and the first Catholic to hold it?",
        "fact": "PT boats; youngest elected president; first Catholic.",
    },
    {
        "question": "Which Vancouver-born actor had his first lead in the teen soap Hillside before starring in Two Guys and a Girl?",
        "fact": "Hillside (1991–1993); Two Guys and a Girl.",
    },
    {
        "question": "Which software suite was announced by Bill Gates at COMDEX on 1 August 1988 with Word, Excel, and PowerPoint as its first three programs?",
        "fact": "Announced 1 Aug 1988 at COMDEX; original three apps.",
    },
    {
        "question": "Which NBA player was drafted 13th by the Charlotte Hornets in 1996, then traded, and spent all 20 seasons with the Lakers?",
        "fact": "13th pick Hornets → Lakers; entire 20-year career there.",
    },
    {
        "question": "Which actor earned his first Oscar nomination for playing a developmentally disabled boy in What's Eating Gilbert Grape?",
        "fact": "First Oscar nom: What's Eating Gilbert Grape (1993).",
    },
    {
        "question": "Which country has ten provinces and three territories stretching from the Atlantic to the Pacific and into the Arctic, making it second-largest by total area?",
        "fact": "10 provinces, 3 territories; second-largest by area. Not Ottawa.",
    },
    {
        "question": "Which singer, born Stefani Germanotta, reached global fame after signing with Interscope in 2007 and releasing The Fame?",
        "fact": "Birth name Stefani Germanotta; Interscope 2007; The Fame.",
    },
    {
        "question": "Which rapper signed with Dr. Dre's Aftermath label after the Slim Shady EP and broke through with The Slim Shady LP in 1999?",
        "fact": "Aftermath via Dr. Dre; The Slim Shady LP (1999).",
    },
    {
        "question": "Which Austrian-born bodybuilder won Mr. Universe at 20, took Mr. Olympia seven times, and later served as California's 38th governor?",
        "fact": "Mr. Universe at 20; seven Mr. Olympia; 38th CA governor.",
    },
    {
        "question": "Which British prime minister led the country through the Second World War, then returned to office from 1951 to 1955?",
        "fact": "PM 1940–1945 and again 1951–1955.",
    },
    {
        "question": "Which West Asian country sits beside Earth's lowest point at the Dead Sea and gained British backing for a Jewish homeland in the 1917 Balfour Declaration?",
        "fact": "Dead Sea / lowest point; Balfour Declaration 1917. Not the capital.",
    },
    {
        "question": "Which actor played Ronon Dex on Stargate Atlantis before appearing as Khal Drogo in the first two seasons of Game of Thrones?",
        "fact": "Ronon Dex then Khal Drogo (seasons 1–2).",
    },
    {
        "question": "Which FIFA World Cup was the first hosted by three countries and the first to use a 48-team field?",
        "fact": "First three-host World Cup; first 48-team edition.",
    },
    {
        "question": "Which actor, famous as Sergio Leone's 'Man with No Name,' served two years as mayor of Carmel-by-the-Sea starting in 1986?",
        "fact": "Dollars Trilogy; mayor of Carmel-by-the-Sea, 1986.",
    },
    {
        "question": "Which Colombian, founder of the Medellín Cartel, was nicknamed the 'King of Cocaine' and estimated at about $30 billion when he died?",
        "fact": "Medellín Cartel; King of Cocaine; ~$30 billion.",
    },
    {
        "question": "Which businessman founded Amazon in 1994 during a road trip from New York City to Seattle after leaving a Wall Street job?",
        "fact": "Founded Amazon mid-1994 on NYC→Seattle road trip.",
    },
    {
        "question": "Which World Cup, the last with 32 teams, was played in November and December to avoid a host country's summer heat?",
        "fact": "Qatar 2022; Nov–Dec; last 32-team tournament.",
    },
    {
        "question": "Which U.S. presidential election had the highest turnout percentage since 1900 and the most votes ever received by a candidate?",
        "fact": "Highest turnout % since 1900; Biden's 81+ million votes.",
    },
    {
        "question": "Which actress became the youngest winner of the Emmy for Outstanding Lead Actress in a Drama Series for playing Rue Bennett?",
        "fact": "Youngest drama-lead Emmy; Rue Bennett on Euphoria.",
    },
    {
        "question": "Which actress, daughter of two actors, won an Emmy for playing Rachel Green on Friends?",
        "fact": "Parents John Aniston and Nancy Dow; Rachel Green Emmy.",
    },
    {
        "question": "Which country is the world's flattest and driest inhabited continent and includes Tasmania plus the mainland?",
        "fact": "Flattest/driest inhabited continent; includes Tasmania. Not the capital.",
    },
    {
        "question": "Which messenger, named to sound like 'what's up,' launched in May 2009 and was later bought by Facebook?",
        "fact": "Name ≈ 'what's up'; launched May 2009; Facebook acquisition.",
    },
    {
        "question": "Which U.S. city is made of five boroughs, each matching a county, and hosts the United Nations headquarters?",
        "fact": "Five boroughs coextensive with counties; UN HQ.",
    },
    {
        "question": "Which cosmologist held Cambridge's Lucasian Professorship of Mathematics from 1979 to 2009 after being diagnosed with motor neurone disease at 21?",
        "fact": "Lucasian Professor 1979–2009; MND diagnosis at 21.",
    },
    {
        "question": "Which film franchise groups its movies into Phases, with the first three together called the Infinity Saga?",
        "fact": "Phases; Infinity Saga = first three phases.",
    },
    {
        "question": "Which physicist won the 1921 Nobel Prize for the photoelectric effect rather than for relativity?",
        "fact": "1921 Nobel for photoelectric effect, not relativity.",
    },
    {
        "question": "Which rapper was known for 'chipmunk soul' beats at Roc-A-Fella before his debut album The College Dropout?",
        "fact": "Chipmunk soul production; The College Dropout (2004).",
    },
    {
        "question": "Which disaster, one of only two rated 7 on the International Nuclear Event Scale, began during a safety test at reactor 4 on 26 April 1986?",
        "fact": "INES 7; reactor 4; 26 April 1986 safety test.",
    },
    {
        "question": "Which kind of website takes its name from a Hawaiian word for 'quick,' via the first such site, WikiWikiWeb?",
        "fact": "Hawaiian 'quick'; WikiWikiWeb as the first example.",
    },
    {
        "question": "Which actor wrote and starred in Rocky (1976) and is one of only two to have a box-office number-one film in six consecutive decades?",
        "fact": "Wrote/starred in Rocky; six-decade #1 films with Harrison Ford.",
    },
    {
        "question": "Which Indian lawyer spent 21 years in South Africa after 1893 and later led a nonviolent campaign for independence from Britain?",
        "fact": "South Africa 1893–c.1914; nonviolent independence campaign.",
    },
    {
        "question": "Which Premier League club was founded in 1878 as Newton Heath LYR Football Club and is nicknamed the Red Devils?",
        "fact": "Newton Heath LYR, 1878; nickname Red Devils.",
    },
    {
        "question": "Which actress, born Norma Jeane Mortenson, began as a pin-up after meeting a photographer while working in a wartime factory?",
        "fact": "Birth name Norma Jeane Mortenson; WWII factory → pin-up.",
    },
    {
        "question": "Which British king reigned only from January to December 1936 before abdicating and becoming Duke of Windsor?",
        "fact": "King Jan–Dec 1936; abdicated; later Duke of Windsor.",
    },
    {
        "question": "Which UEFA club competition began in 1955 as the European Champion Clubs' Cup?",
        "fact": "Introduced 1955 as the European Cup.",
    },
    {
        "question": "Which Pacific island country is divided into 47 prefectures, with about 75 percent of its land mountainous and forested?",
        "fact": "47 prefectures; ~75% mountainous/forested. Not the capital.",
    },
    {
        "question": "Which entertainer was a Fly Girl on In Living Color before her leading role in the 1997 film Selena?",
        "fact": "In Living Color Fly Girl; Selena (1997).",
    },
    {
        "question": "Which first lady is the first naturalized U.S. citizen and first non-native English speaker to hold the role?",
        "fact": "First naturalized citizen and first non-native English speaker as first lady.",
    },
    {
        "question": "Which media personality's family reality show began after a 2007 tape, and who later founded the shapewear company Skims?",
        "fact": "KUWTK after 2007 tape; founded Skims in 2019.",
    },
    {
        "question": "Which 2019 Marvel film, the 22nd in the MCU, is a direct sequel in which surviving heroes try to undo Thanos erasing half of all life?",
        "fact": "22nd MCU film; direct sequel to Infinity War; reverse the snap.",
    },
    {
        "question": "Which actor first drew wide notice as a cowboy hitchhiker in Thelma & Louise?",
        "fact": "Cowboy hitchhiker in Thelma & Louise (1991).",
    },
    {
        "question": "Which English singer signed with Warner Bros. Records in 2014 after working as a model, then topped the UK chart with 'New Rules'?",
        "fact": "Model then Warner 2014; UK #1 'New Rules'.",
    },
    {
        "question": "Which actress won an Oscar for Girl, Interrupted (1999) before starring as Lara Croft in 2001?",
        "fact": "Oscar: Girl, Interrupted; then Lara Croft: Tomb Raider.",
    },
    {
        "question": "Which BBC service is the world's largest external broadcaster by reach and airs radio in more than 40 languages?",
        "fact": "Largest external broadcaster; 40+ languages.",
    },
    {
        "question": "Which island country sits about one degree north of the equator and was established as a British entrepôt by Stamford Raffles in 1819?",
        "fact": "~1° N of equator; Raffles 1819 entrepôt. City-state, not a capital-of-X trap.",
    },
]


HEADER = """# Grand Goal questions — English top 100 (draft)

Hand-check this list. Nothing here is wired into the game yet.

## How these were picked

- Ranked by all-time visits in `world/pageviews/pageviews_aggregate_en.json` (`top_by_sum`, 2016-07 to 2026-06).
- Kept only titles that exist in `pool_en.json`.
- Dropped sensitive titles, lists/portals/Wikipedia-namespace, and obvious junk (`404.php`, adult domains).
- One question per remaining page, from that page's **lead** (Wikipedia intro).

Skipped examples at the top of the ranking: Featured pictures, XHamster, Current events portal, 404.php, MCU film list, Jeffrey Dahmer, Pornhub, Russia (tagged sensitive), 9/11.

Worth a hard look while reviewing: the three **xXx** movie pages (search-traffic pollution), plus **Jeffrey Epstein**, **Adolf Hitler**, and **Pablo Escobar**. The questions follow the rules; the pages may still be bad Grand Goals.

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

Leads were fetched on 2026-08-17 and truncated. If Wikipedia moved, trust the live intro.

---
"""


def first_paragraph(lead: str) -> str:
    text = " ".join((lead or "").split())
    if not text:
        return "_(no lead fetched)_"
    if len(text) > 520:
        text = text[:520].rsplit(" ", 1)[0] + "…"
    return text


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    entries = data["entries"]
    if len(entries) != 100:
        raise SystemExit(f"expected 100 source entries, got {len(entries)}")
    if len(QUESTIONS) != 100:
        raise SystemExit(f"expected 100 questions, got {len(QUESTIONS)}")

    chunks = [HEADER]
    for src, q in zip(entries, QUESTIONS):
        rank = int(src["rank"])
        title = src["title"]
        tags = ", ".join(src.get("tags") or [])
        views = src.get("views_summed_from_monthly_tops")
        chunks.append(
            f"## {rank:03d}. {title}\n\n"
            f"- **Answer page:** [{title}](https://en.wikipedia.org/wiki/{title.replace(' ', '_')})\n"
            f"- **Tags:** {tags}\n"
            f"- **Pageviews sum (monthly tops):** {views:,}\n"
            f"- **Question:** {q['question']}\n"
            f"- **Lead fact used:** {q['fact']}\n"
            f"- **Lead (excerpt):** {first_paragraph(src.get('lead') or '')}\n"
            f"- **Validate:** [ ] accept &nbsp; [ ] edit &nbsp; [ ] reject\n"
            f"- **Notes:**\n"
        )
    OUT.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
