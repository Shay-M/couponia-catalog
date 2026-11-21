<div dir="rtl">

# Couponia Catalog v3.3 — הרחבת רשימות רשתות ממקורות רשמיים

## מה חדש

זו **חבילה מצטברת**, הכוללת את קובצי v3.2 ואת השינויים של v3.3. אם המאגר הציבורי עדיין ב־v3.1, אפשר להתקין את v3.3 ישירות — אין צורך לפרסם קודם את v3.2.

- **Gift Card MAX:** נוספו 18 קשרי כרטיס–רשת, על סמך עלון רשמי של MAX עבור מוצר זה בלבד.
- **Super Gift Card MAX:** נוספו 20 קשרים נוספים מעלון רשמי **נפרד**; מוצר זה כולל גם רשתות מזון. לא העתקנו את הרשימה אוטומטית בין שני הכרטיסים.
- **Gifta:** נוספו שמונה רשתות מתוך מדגם הלוגואים בעמוד המנפיק. **Gifta Food** עדיין ללא קשרי חנויות מאומתים, כי רשימת המזון הנפרדת לא נבדקה באופן אמין.
- **Gift Card Isracard Digital:** מוצר כרטיס חדש ו־14 קשרי רשתות מדף המוצר הייעודי.
- **Gift Card Isracard Shopping:** מוצר כרטיס חדש ו־14 קשרי רשתות מדף המוצר הייעודי.
- קוד היבוא מאפשר כעת `restrictionNote` ברמת רשת בודדת, כדי לתעד מגבלה שמפורסמת בעלון המקורי, בלי להציג מימוש מובטח.

### ספירות צפויות

| מדד | ב־v3.1 (המאגר המקורי) | ב־v3.2 | אחרי v3.3 |
|---|---:|---:|---:|
| סוגי כרטיסים | 99 | 105 | **107** |
| עסקים | 409 | 424 | **445** |
| שיוכי כרטיס–עסק | 504 | 532 | **606** |

המספרים חושבו בבדיקת בנייה מקומית מתוך ה־JSON הבסיסי הכלול באפליקציית Android (99/409/504). ה־Action יבנה מחדש מתוך `seed/catalog-v2.db` שב־GitHub ויאשר את הספירות בבדיקות CI לפני פרסום. עשויים להיות הבדלי ספירה אם שינית ידנית את קובץ ה־seed.

**דגש:** כל קשר מתועד כ־`listed` (מופיע ברשימת המנפיק), **לא** כ־"עבר תשלום בקופה". היעדר קשר משמעו "לא ידוע", ולא "הכרטיס לא מכובד". יש לבדוק תנאי סניף, אתר מסחר, מבצעים וכרטיס פיזי/דיגיטלי לפני שימוש.

## מקורות המנפיקים שנבדקו

1. **MAX Gift Card** — https://www.max.co.il/SharedMedia/24100/gc-max-digital.pdf
2. **MAX Super Gift Card** — https://www.max.co.il/SharedMedia/24087/gc-max-super.pdf
3. **Isracard Digital Gift Card** — https://www.isracard.co.il/credit-cards/digital-gift-card
4. **Isracard Gift Card Shopping** — https://www.isracard.co.il/credit-cards/gift-card-shopping
5. **Gifta** — https://gifta.co.il/גיפטא-פוד/ — רק מדגם הלוגואים המוגדר "רשתות המכבדות גיפטא" בעמוד, ולא רשימת Gifta Food
6. כל ששת מוצרי v3.2 נשמרים, והמקורות שלהם עדיין מופיעים ב־`config/curated_issuer_facts.json`.

המאגר כולל **רק מדגם שמות קצר שנבדק ידנית** מכל מקור; אינו מחליף רשימת רשתות חיה ואינו משחזר את תוכן העלונים. אין להפעיל סריקה/העתקה אוטומטית של מסדי נתונים של צד שלישי בלי בדיקת תנאי שימוש והרשאת הפצה.

## בדיקה חוזרת ב־GitHub

1. פתח ב־GitHub Desktop את `Shay-M/couponia-catalog` על `master`.
2. חלץ את **Couponia_Catalog_v3_3_GitHub_Update.zip** לתיקיית השורש של ה־Repository, כולל תיקיית `.github` החבויה. אשר החלפת קבצים קיימים. **אל תמחק את `seed/`, `src/release.py`, `src/watch_sources.py` או בדיקות קיימות** — קבצים אלה אינם בחבילת העדכון המצומצמת.
3. בצע Commit, ואז Push origin.
4. עבור ל־Actions והפעל `Build unified Israeli gift-card catalog` בענף `master`.
5. בודקים שהשלב `Run tests` עבר ושמופיעות הספירות `107 / 445 / 606` תחת `Build new snapshot from authorized sources` או בהמשך תוצאות הפרסום.
6. בדוק ש־`Compare with last published catalog` החזיר `coreChanged: true`, ולאחר מכן פתח:
   https://shay-m.github.io/couponia-catalog/v3/manifest.json
7. באפליקציית Android: **הגדרות > מאגר תווי קנייה וחנויות > בדוק עדכונים עכשיו**. אין צורך להתקין APK חדש, לשנות Manifest URL, או למחוק נתונים אישיים.

להרצה מקומית **מתוך ה־Repository המלא**:

```bash
python -m unittest discover -s tests -v
python src/build.py --seed seed/catalog-v2.db --curated-file config/curated_issuer_facts.json --out dist/v3
python -m src.review_status --curated-file config/curated_issuer_facts.json
```

## ממצאי החיפוש המחודש ב־GitHub

- https://github.com/yhyatt/ClawSavings — כבר מחובר כיבוא אוטומטי של **מועמדים להטבות** בלבד; נתונים אלו אינם קשרי כיבוד כרטיס בקופה.
- https://github.com/eladkishon/buyme-mcp — מאגר BUYME שיכול לעזור באיתור שמות וספקים. **לא הועתק ולא הופעל יבוא פרסומי** כי אין אישור הפצה ברור מהבעלים של המידע.
- https://github.com/aviv943/restaurants-il — רעיון לאיחוד/נרמול מסעדות ומקורות בלבד; בפרויקט מצוין ששימושו אינו מיועד להפצה מחדש.
- אתרים משניים שמפרסמים אלפי קשרי כרטיס–עסק יכולים לעזור בגילוי מקורות, אך לא הוספנו מהם שיוך בלי אימות מול המנפיק והבהרת זכויות השימוש.

### מה כדאי לבדוק לאחר הפרסום

מומלץ לבחון דרך מורשית לקבלת קובץ רשימות החנויות של Gifta (האתר מציע הורדת Excel), ואז רשימת שיוכים מדויקת של Swish Plus ותו הזהב; אין לצרף רשימות ממקור אחר באופן אוטומטי בלי לשייך אותן לסוג הכרטיס המדויק. מידע שהמנפיק לא מבסס יישאר "מועמד לבדיקה" בלבד.

</div>
