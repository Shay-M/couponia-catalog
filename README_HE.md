# הגרסה הנוכחית — Stage 5.6

הוראות ותיאור השינויים נמצאים ב־[docs/UPDATE_STAGE56_HE.md](docs/UPDATE_STAGE56_HE.md). חבילה זו כוללת את ה־seed המקורי ואת כל קובצי המחולל הנדרשים. נתוני `dist` נוצרים בבנייה ואינם כלולים בחבילת המקור. הסעיפים הישנים בהמשך נשמרים כהיסטוריית עדכונים.

**Couponia v3.4 (2026-11-21):** Product-scoped issuer review added for existing BUYME cards; GiftZone HTZone curated sample; official Swish Plus product URL; additive catalog guard; disabled credit-benefits groundwork. Local preview: **108 products, 462 merchants, 648 links**. See [v3.4 installation and verification](docs/UPDATE_v34.md). No Android changes or live offer ingestion.

<div dir="rtl">

**עדכון 21.11.2026 — v3.3:** נוספו שני מוצרי ישראכרט נוספים, שיוכים נפרדים לשני מוצרי MAX, ומדגם Gifta. גרסה מצטברת: 107 כרטיסים / 445 עסקים / 606 שיוכים. ראו [הוראות v3.3](docs/UPDATE_v33_HE.md).

**עדכון 21.11.2026 — v3.2:** נוספו 6 סוגי תווים ו־28 שיוכים ממדגם בדיקה של שני מוצרי ישראכרט; אין שינוי בפורמט Android. ראו [הוראות עדכון v3.2](docs/UPDATE_v32_HE.md).

**עדכון נובמבר 2026 — v3.1:** התווסף מנגנון פרסום יציב שנמנע מעדכונים חוזרים כשאין שינוי, ומפריד גרסת רשימות היישום מגרסת הטבות לא מאומתות. ראו [הוראות עדכון v3.1](docs/UPDATE_v31_HE.md).

</div>

# מאגר תווי קנייה מרכזי — GitHub Actions / SQLite / JSON

**POC v3 — מבוסס על מאגר v2 שהכנו קודם.** המערכת בנויה על מקורות נפרדים, מאחדת נתונים בצורה שמרנית, ומפרידה בין שיוכים שפורסמו במאגר לבין **מועמדים לאימות** המגיעים מפרויקטים אחרים.

## מה יש בחבילה

- `seed/catalog-v2.db` — 99 כרטיסים, 409 עסקים, 504 קשרים; רשימה חלקית שתוקפה תלוי בתאריך ומקור כל קשר.
- `src/build.py` — מחולל SQLite v3 ותוצרי JSON ליישום Android.
- `.github/workflows/publish-catalog.yml` — בדיקות והפקה יומית של JSON ו-SQLite, פרסום דרך GitHub Pages.
- `tests/` — בדיקות אוטומטיות לבחינת שמירת בסיס הנתונים, סינון מידע ישן והגנה ממיפוי שגוי.
- `dist/v3/` — תוצר **שנבנה ב־GitHub Actions**; אין צורך להעלות ידנית קבצים מיושנים מה־ZIP. אפשר לבנות Preview מקומי בלי רשת, אך הוא לא יכלול את הטבות ClawSavings החיות.

## מה בדקנו בפרויקטי GitHub

| פרויקט | שימוש אפשרי | החלטה |
| --- | --- | --- |
| https://github.com/eladkishon/buyme-mcp | קטלוג BUYME ALL: `data/buyme.json`, איסוף שבועי, פרטי ספקים | מתאם יבוא אופציונלי, מועמדים בלבד. לא להעתיק או לפרסם נתונים בלי בירור זכויות |
| https://github.com/yhyatt/ClawSavings | `discounts.json` — הייטקזון/פועלים Wonder/קטגוריות/מבצעים | Action מושך ציבורית ומסמן הטבות **לא מאומתות**, עם תאריך מדויק |
| https://github.com/aviv943/restaurants-il | התאמת מסעדות מ-Tabit, Ontopo, BUYME ו-HTZone | רעיון לארכיטקטורת דה-דופליקציה בלבד. README מסייג: all rights reserved |

**הפרדה עקרונית:** במקור ClawSavings שיוך של מועדון לקטגוריית אופנה **לא מוכיח** שכל חנות בקטגוריה מקבלת את הכרטיס! אנו מייבאים רק פרטי הטבות נקודתיות עם שם חנות, וגם אותן כרשומות `unverified`.

## הפעלה

```bash
python -m unittest discover -s tests -v
python src/build.py --seed seed/catalog-v2.db --curated-file config/curated_issuer_facts.json --out dist/v3
```

טעינה ישירה של נתוני ClawSavings (נדרש אינטרנט):

```bash
python src/build.py --seed seed/catalog-v2.db \
  --clawsavings-url https://raw.githubusercontent.com/yhyatt/ClawSavings/main/discounts.json \
  --out dist/v3
```

יבוא מקומי אופציונלי של BUYME לצורכי בדיקה — **רק לאחר בירור הרשאה לשימוש במאגר זה**:

```bash
python src/build.py --seed seed/catalog-v2.db \
  --buyme-file my-licensed-buyme.json --out dist/v3
```

היבוא מוסיף רק `acceptance_candidates`. הוא **אינו** משנה את `card_merchants`, ולכן לא יציג כיבוד כרטיס כעובדה בלי אימות.

## הפעלה ב-GitHub

1. צור Repository עצמאי והעלה את תוכן התיקייה הזו (כולל `.github`).
2. תחת Settings → Pages בחר **GitHub Actions** כמקור הפריסה.
3. פתח Actions והפעל `Build unified Israeli gift-card catalog` באמצעות `Run workflow`.
4. בסיום, הכתובת תהיה במבנה `https://USERNAME.github.io/REPO/v3/manifest.json`, וקובץ `catalog.db` באותו נתיב. הכתובת לא קיימת לפני הפרסום הראשון.

אם ה-Action נכשל במשיכה או בבדיקות, הפרסום מתבטל והגרסה הקודמת נשארת ב-Pages. GitHub מתזמן ריצות במתכונת best effort ויכול לעכב אותן.

## שימוש באפליקציית Android

- `catalog.db` כולל *תוספת* של הטבלאות `external_sources`, `benefit_candidates` ו-`acceptance_candidates`; הסכמה כעת גרסה 3.
- ב-Room יש ליצור Entities/Migration המתאימים לגרסה 3. אם אין שינוי סכמת Room כרגע, אפשר להמשיך לצרוך את ה-v2 הקיים, ובנפרד את קובצי JSON של ההטבות.
- `manifest.json` מכיל `dataVersion`, `catalogSha256`, `schemaVersion` וספירת פריטים. יש לבדוק checksum ולהחליף DB רק באופן אטומי ולא למחוק נתוני משתמש.
- יש להציג `unverified` והטבות `stale` כמידע לבדיקה, לא כתשלום ודאי בקופה. אין להסיק 'לא מכבדים' מחוסר במידע.

## מגבלות ושלבים מומלצים

- אין פה עדיין איסוף ישיר מהאתרים הרשמיים של HappyGift, תו הזהב ו-Swish. הנתונים האלה נשארו מגרסה 2.
- אין כרגע יכולת לאמת נתוני שטראוס+ אישיים מתוך חשבון של משתמש, ואין לשמור אישורי התחברות במאגר ציבורי.
- BUYME ALL הוא מוצר ספציפי; לא נכון להסיק שכל אחד מ-1,200+ העסקים במאגר צד שלישי מכבד גם כל כרטיס BUYME אחר.
- יש להוסיף מתאמים לפי מוצר כרטיס, להצליב עם רשימות המנפיקים, לתעד היתרי שימוש ולהגדיר ספי חריגה מחמירים לפני פרסום עדכון אוטומטי.

<div dir="rtl">

## התאמה ל־Couponia שלב 3

בגרסת ההפצה הנוכחית `manifest.json` מכיל `fileSha256` לשלושת קובצי הנתונים `cards.json`, `merchants.json`, `acceptance.json` ומספר `dataVersion` בפורמט זמן המאפשר עדכונים חוזרים גם באותו יום. האפליקציה דורשת את השדות האלה כדי להפעיל סנכרון מאובטח ונמנעת מעדכון אם אינם קיימים. אין להשתמש בגרסת Repo ישנה שאינה מייצרת אותם.

הקטלוג המפורסם דרך GitHub Pages זמין בדרך כלל תחת `/v3/manifest.json`, כי ה־Action מפרסם את תיקיית `dist` ומאחסן בתוכה את `v3`.

הרשאות לסקרייפינג ולהפצה מחדש הן באחריות בעל המאגר. מועמדים לא מאומתים ממועדוני הטבות **אינם** מתווספים לטבלת הקשרים המאושרים לתצוגת חנויות באפליקציה.

</div>
