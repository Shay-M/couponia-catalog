<div dir="rtl">

# Couponia Catalog — גרסה 3.2: הרחבת נתונים שמרנית

## מה התווסף

- **6 סוגי כרטיסים חדשים** מתוך דפי מנפיק רשמיים: שני מוצרי Gift Card נפרדים של ישראכרט, שני מוצרי Gift Card של MAX, וכרטיסי Gifta ו-Gifta Food.
- **28 שיוכי כרטיס–עסק חדשים** לשני מוצרי ישראכרט, מתוך מדגם קטן של שמות עסקים שפורסם בדפי המוצרים של ישראכרט. שיוך מסומן `listed` ולא "מכובד בקופה בוודאות".
- **מנגנון נרמול מותגים משותף**, המונע יצירת מותג נוסף כאשר קיימת התאמה מפורשת, למשל `ניין ווסט` ו־`NINE WEST`.
- **רשומת מקור ותאריך בדיקה** לכל כרטיס ושיוך שנוספו.
- **אזהרת רעננות**: ה־Action יתריע לאחר 60 יום בלי בדיקה מחדש של הרשימות הידניות; הוא לא יעדכן אותן באופן שקרי.
- 9 בדיקות נוספות שמכסות מניעת כפילויות, הפרדה בין שני מוצרי ישראכרט, הגנה מסכמת HTTPS פגומה ובדיקת גרסאות.

### סיכום נתונים צפוי אחרי Action

| פריט | לפני | אחרי |
| --- | ---: | ---: |
| כרטיסים | 99 | **105** |
| עסקים | 409 | **424** |
| שיוכי כרטיס לעסק | 504 | **532** |
| מועמדים להטבות ClawSavings | 38 בהרצה הקודמת | תלוי במקור החיצוני |

**הערה**: חלק מהכרטיסים החדשים אינם כוללים עדיין רשימת חנויות. לא הסקנו קבלה מחלוקת מותגים משפחתית. נתונים מ־BUYME אינם מועתקים, משום שעדיין לא התקבלה הרשאה להפצה מחדש של המאגר.

## כיצד מעדכנים ב־GitHub

עבור `Shay-M/couponia-catalog` בענף **`master`**:

1. בצע Clone ב־GitHub Desktop, או פתח את העותק המקומי הקיים.
2. חלץ **Couponia_Catalog_v3_2_GitHub_Update.zip** לתוך שורש ה־Repository, כולל התיקייה החבויה `.github`. אשר החלפת קובצי המקור שהשתנו.
3. אין צורך למחוק `seed/` או לשנות ידנית את `dist/`. ה־Action ייצור את הנתונים המתפרסמים מחדש.
4. ב־GitHub Desktop בצע Commit ו־Push ל־`master`.
5. ב־Actions הפעל `Build unified Israeli gift-card catalog` באמצעות Run workflow על `master`.
6. חפש בלוג `Build new snapshot from authorized sources` ספירה של `105` כרטיסים, `424` עסקים ו־`532` שיוכים. שלב `Compare with last published catalog` אמור להחזיר `coreChanged: true`, כי הוספנו נתונים אמיתיים.
7. בדוק את: `https://shay-m.github.io/couponia-catalog/v3/manifest.json`.
8. ב־Couponia פתח **הגדרות > מאגר תווי קנייה וחנויות > בדוק עדכונים עכשיו**. מספר הכרטיסים אמור לגדול ל־105. אין צורך בעדכון APK.

### הרצה מקומית ללא אינטרנט

```bash
python -m unittest discover -s tests -v
python src/build.py --seed seed/catalog-v2.db --curated-file config/curated_issuer_facts.json --out dist/v3
python -m src.review_status --curated-file config/curated_issuer_facts.json
```

לאחר פרסום ראשון, הרצה נוספת ללא שינוי בתוכן אמורה להחזיר `changed: false` ולדלג על Deploy.

## מקורות המידע החדשים

- `https://www.isracard.co.il/credit-cards/gift-card` — מוצר Gift Card, מדגם 14 עסקים.
- `https://www.isracard.co.il/credit-cards/gift-card-isracard` — מוצר Gift Card Isracard, מדגם 14 עסקים אחרים.
- `https://www.max.co.il/cards/giftcards` — דפי מוצר MAX, ללא מיפוי חנויות עדיין.
- `https://gifta.co.il/שאלות-ותשובות-2/` ו־`https://gifta.co.il/גיפטא-פוד/` — מידע על סוגי כרטיסים, ללא מיפוי חנויות עדיין.

קובץ הנתונים `config/curated_issuer_facts.json` הוא רשימת עובדות קצרה שנבדקה ידנית, לא סקרייפר ולא העתקה של מאגר שלם. אין בכך אישור אוטומטי לשימוש מסחרי בכל תוכן של מנפיק. לפני הרחבה כמותית/אוטומטית של מקור נדרש בירור תנאי שימוש והרשאות.

## מבנה ו־SOLID

- `src/identity.py`: התאמה ודאית למותגים, ללא ניחוש fuzzy.
- `src/curation.py`: אימות והכנסה שמרנית של עובדות מנפיק.
- `src/build.py`: מחולל התוצר השלם (ללא תלות ישירה במנגנון האישור).
- `src/release.py`: שומר על `dataVersion` ללא שינוי כשלא השתנו קובצי ליבה.
- `src/review_status.py`: תזכורת לנתונים שאינם רעננים, ללא מחיקת מידע.

**אין שינוי ב־schemaVersion (נשאר 3)**, בכתובת ה־Manifest או ב־JSON schema שהאפליקציה צורכת.

</div>
