"""High-precision completion-claim detection (English + Ukrainian).

A claim is an affirmative, present/past-tense statement in the assistant's own
voice. Missing a claim costs nothing; inventing one annoys a user, so every
doubt resolves to "no claim". Each pattern carries the example it was written
for; tests/test_claims.py checks that every example still matches.

Claim types: tests_pass, done, fixed, verified, deployed.
"""
import re
from collections import namedtuple

P = namedtuple("P", "type rx example")
I = re.I | re.U

PATTERNS = [
    # --- tests_pass ---------------------------------------------------------
    P("tests_pass", r"\b(?:all\s+)?(?:\d+\s+)?(?:of\s+the\s+)?(?:\w+[\s-]){0,2}?tests?\s+(?:now\s+|still\s+|all\s+)?"
                    r"(?:pass(?:es|ed)?|are\s+(?:now\s+)?(?:passing|green)|is\s+(?:now\s+)?(?:passing|green)|succeed(?:ed|s)?)\b",
      "All tests pass."),
    P("tests_pass", r"\b(?:test\s+suite|suite|pytest|jest|vitest|ci|the\s+build)\s+(?:now\s+)?"
                    r"(?:pass(?:es|ed)?|is\s+(?:now\s+)?(?:green|passing)|succeeded)\b",
      "The test suite passes."),
    P("tests_pass", r"\b(\d+)(?:/\1)?\s+(?:tests?\s+)?pass(?:ed|ing)\b(?![^.]*\b[1-9]\d*\s+(?:failed|failing|errors?)\b)",
      "42 passed, 0 failed."),
    P("tests_pass", r"\b(?:test_\w+|\w+_test|[\w-]+\.(?:spec|test)\.\w+|\w+Tests?)\s+(?:now\s+)?pass(?:es|ed)\b",
      "test_login passes now."),
    P("tests_pass", r"\beverything\s+(?:is\s+)?(?:green|passes|passing)\b", "Everything is green."),
    P("tests_pass", r"\bshould\s+now\s+pass\b", "The tests should now pass."),
    P("tests_pass", r"(?:усі|всі)?\s*(?:\d+\s+)?(?:\w+\s+)?тест(?:и|ів)?\s+(?:тепер\s+|успішно\s+)?"
                    r"(?:проходять|пройшли|пройдено|зелені|проходить|пройшов)", "Усі тести проходять."),
    P("tests_pass", r"\bтести\s+(?:в|у)\s+зеленому\b", "Тести в зеленому."),

    # --- done ---------------------------------------------------------------
    P("done", r"^(?:all\s+)?done(?:\s*[.!:—–-]|$)", "Done."),
    P("done", r"\bi(?:'ve|\s+have)?\s+(?:finished|completed|implemented|wrapped\s+up)\b", "I've implemented the endpoint."),
    P("done", r"\b(?:task|implementation|work|feature|change|changes|refactor(?:ing)?|migration|everything)\s+"
              r"(?:is|are)\s+(?:now\s+)?(?:complete|completed|done|finished|in\s+place)\b",
      "The migration is complete."),
    P("done", r"^(?:готово|зроблено|завершено|виконано)(?:\s*[.!:—–-]|$)", "Готово."),
    P("done", r"\b(?:я\s+)?(?:завершив|завершила|закінчив|закінчила|реалізував|реалізувала|імплементував|імплементувала)\b",
      "Я реалізував ендпоінт."),
    P("done", r"\b(?:завдання|задача|робота|реалізація|міграція)\s+(?:виконан[аео]|завершен[аео]|готов[аеі])\b",
      "Завдання виконано."),

    # --- fixed --------------------------------------------------------------
    P("fixed", r"\bi(?:'ve|\s+have)?\s+(?:fixed|resolved|patched)\b", "I fixed the null check."),
    P("fixed", r"^(?:fixed|resolved)\b(?!\s+(?:in|by|as)\b)", "Fixed the off-by-one in the pager."),
    P("fixed", r"\b(?:bug|issue|error|problem|crash|regression|failure|leak)\s+(?:is|has\s+been|was)\s+(?:now\s+)?(?:fixed|resolved|gone)\b",
      "The bug is fixed."),
    P("fixed", r"\b(?:this|that|it|the\s+change)\s+(?:should\s+)?(?:now\s+)?(?:fixes|resolves)\b", "This fixes the race."),
    P("fixed", r"\b(?:this|that|the\s+change)\s+should\s+(?:now\s+)?(?:fix|resolve)\b", "That should fix it."),
    P("fixed", r"\b(?:я\s+)?(?:виправив|виправила|пофіксив|пофіксила|полагодив|полагодила)\b", "Виправив null-перевірку."),
    P("fixed", r"\b(?:баг|помилк[ау]|проблем[ау]|падіння)\s+(?:виправлено|усунено|вирішено|пофікшено)\b", "Баг виправлено."),
    P("fixed", r"^(?:виправлено|пофікшено)\b", "Виправлено: пагінація."),

    # --- verified -----------------------------------------------------------
    P("verified", r"\bi(?:'ve|\s+have)?\s+(?:verified|confirmed|double-checked|tested)\b", "I verified the redirect."),
    P("verified", r"^verified\b", "Verified: the cache is invalidated."),
    P("verified", r"\b(?:it|this|everything|the(?:\s+[\w-]+){1,3})\s+(?:now\s+)?works\s+(?:as\s+expected|correctly|now|fine|end[\s-]to[\s-]end)\b",
      "Everything works as expected."),
    P("verified", r"\b(?:it|this|everything|the(?:\s+[\w-]+){1,3})\s+is\s+(?:now\s+)?working\s+(?:as\s+expected|correctly|now)\b",
      "The login flow is working correctly."),
    P("verified", r"\b(?:я\s+)?(?:перевірив|перевірила|протестував|протестувала|підтвердив|підтвердила)\b", "Перевірив редірект."),
    P("verified", r"\b(?:все|усе|воно|це)\s+(?:тепер\s+)?працює(?:\s+(?:коректно|правильно|як\s+очікувалось))?\b",
      "Все працює коректно."),
    P("verified", r"^перевірено\b", "Перевірено."),

    # --- deployed -----------------------------------------------------------
    P("deployed", r"\bi(?:'ve|\s+have)?\s+(?:deployed|shipped|released|published)\b", "I deployed it to staging."),
    P("deployed", r"\b(?:has\s+been|was|is\s+now|successfully)\s+(?:deployed|released|shipped)\b", "The fix was deployed to production."),
    P("deployed", r"^(?:deployed|shipped|released)\b(?!\s+(?:in|by|as)\b)", "Shipped to production."),
    P("deployed", r"\bis\s+(?:now\s+)?live\s+(?:on|at|in)\b", "It is now live at the staging URL."),
    P("deployed", r"\b(?:я\s+)?(?:задеплоїв|задеплоїла|розгорнув|розгорнула|викатив|викатила)\b", "Задеплоїв на staging."),
    P("deployed", r"\b(?:задеплоєно|розгорнуто|викачено)\b", "Розгорнуто в прод."),
]
COMPILED = [(p.type, re.compile(p.rx, I)) for p in PATTERNS]

# A sentence that contains any of these is never a claim.
NEGATION = re.compile(
    r"\b(?:not|never|nothing|cannot|unable|nor|yet|neither|no\s+longer)\b|n't\b|n’t\b|"
    r"(?:^|\s)(?:не|ні|ще\s+не|жоден|жодн\w+|немає|нема)(?=\s|$|[,.!])", I)
FUTURE = re.compile(
    r"\b(?:will|shall|would|could|might|may|gonna|going\s+to|about\s+to|plan\s+to|need\s+to|needs\s+to|"
    r"want\s+to|try\s+to|let\s+me|let's|next,?\s+i|intend|hopefully|probably|likely|"
    r"supposed\s+to|expect(?:ed|s)?\s+to)\b|\bexpected\s*:|'ll\b|’ll\b|"
    r"(?:^|\s)(?:запущу|перевірю|виправлю|зроблю|задеплою|допишу|буду|будуть|збираюся|планую|спробую|"
    r"потрібно|треба|має|мають|повинн\w+|мабуть|можливо|далі|потім|зараз\s+\w+у)(?=\s|$|[,.!])", I)
CONDITIONAL = re.compile(
    r"\b(?:if|once|when|whenever|unless|until|assuming|as\s+soon\s+as|whether|after\s+you)\b|"
    r"(?:^|\s)(?:якщо|коли|як\s+тільки|щойно\s+(?:ви|ти)|доки|поки)(?=\s|$|[,.!])", I)
HEARSAY = re.compile(
    r"\b(?:you\s+(?:said|mentioned|wrote|asked|claimed)|according\s+to|the\s+user|previously|earlier|"
    r"used\s+to|originally|before\s+(?:my|the|this)\s+change)\b|(?:^|\s)(?:ви\s+казали|раніше)(?=\s|$|[,.!])", I)
QUESTION_START = re.compile(
    r"^(?:do|does|did|can|could|should|would|is|are|was|were|have|has|shall|will|чи)\b", I)
IMPERATIVE_START = re.compile(
    r"^(?:run|re-?run|make\s+sure|ensure|check|verify|confirm|fix|deploy|test|add|update|try|please|"
    r"go\s+ahead|запусти|перевір|виправ|задеплой|додай|онови|спробуй)\b", I)
# Words right before a tests-pass match that turn it into a goal ("to make the tests pass").
GOAL_BEFORE = re.compile(r"(?:\bto|\bmake|\bmakes|\bmaking|\bget|\bensure|\bensuring|\bso|\bthat|\buntil|щоб|аби)\s+"
                         r"(?:\w+\s+){0,3}$", I)
FAILED_COUNT = re.compile(r"\b[1-9]\d*\s+(?:failed|failing|failures?|errors?)\b|(?<!\b0 )(?<!\bno )\b(?:fail(?:s|ed|ing|ures?)?|впал\w*|падає)\b", I)
PLAN_HEADER = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*)?(?:plan|next\s+steps?|todo|to-?do|remaining|follow-?ups?|open\s+questions|"
    r"план|наступні\s+кроки|що\s+далі|залишилось|залишилося)(?:\*\*)?\s*:?\s*(?:\*\*)?\s*$", I)
PARTIAL_WORDS = re.compile(r"\b(?:new|relevant|related|affected|targeted|these|those|modified|updated|"
                           r"specific|added|нові|відповідні)\b|[A-Za-z][\w-]*(?:_|::|\.)[A-Za-z]\w*", I)


def _clean(text):
    text = re.sub(r"```.*?(?:```|\Z)", "\n", text, flags=re.S)       # code blocks
    text = re.sub(r"[\"“«„][^\"”»“\n]{1,400}[\"”»“]", " ", text)       # quoted text
    return text


def sentences(text):
    """Yield candidate sentences, skipping blockquotes and plan/todo sections."""
    in_plan = False
    for raw in _clean(text or "").splitlines():
        line = raw.strip()
        if not line:
            in_plan = False
            continue
        if PLAN_HEADER.match(line):
            in_plan = True
            continue
        if line.startswith("#"):
            in_plan = False
        if line.startswith(">") or re.match(r"^[-*+]\s*\[[ xX]?\]", line):
            continue
        bullet = re.match(r"^(?:[-*+•]|\d+[.)])\s+", line)
        if bullet and in_plan:
            continue
        line = re.sub(r"^(?:#+|[-*+•]|\d+[.)])\s*", "", line).replace("**", "")
        for part in re.split(r"(?<=[.!?])\s+|;\s+|\s+(?:but|however|although|though|але|проте|однак)\s+", line):
            part = part.strip(" \t*_")
            if part:
                yield part


def _skip(sentence):
    s = sentence.strip()
    return (s.endswith("?") or QUESTION_START.match(s) or IMPERATIVE_START.match(s)
            or NEGATION.search(s) or FUTURE.search(s) or CONDITIONAL.search(s) or HEARSAY.search(s))


def _scope(sentence):
    if PARTIAL_WORDS.search(sentence) and not re.search(r"\b(?:all|every|усі|всі)\b", sentence, I):
        return "partial"
    return "all"


def extract(message):
    """Return [{'type', 'scope'}], at most one per type.

    >>> [c["type"] for c in extract("Fixed the pager. All 12 tests pass.")]
    ['fixed', 'tests_pass']
    >>> extract("I'll run the tests next.")
    []
    """
    found = {}
    for sentence in sentences(message):
        if _skip(sentence):
            continue
        for ctype, rx in COMPILED:
            if ctype in found:
                continue
            m = rx.search(sentence)
            if not m:
                continue
            if ctype == "tests_pass" and (GOAL_BEFORE.search(sentence[:m.start()]) or FAILED_COUNT.search(sentence)):
                continue
            scope = _scope(sentence) if ctype == "tests_pass" else None
            found[ctype] = {"type": ctype, "scope": scope}
    order = ["tests_pass", "done", "fixed", "verified", "deployed"]
    return sorted(found.values(), key=lambda c: order.index(c["type"]))
