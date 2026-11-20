# התקנת Couponia Catalog על GitHub Pages

1. צור Repository ציבורי בשם `couponia-catalog` ללא README / .gitignore נוספים.
2. חלץ את חבילת ZIP; העלה ל-Repository את **תוכן** תיקיית `catalog_server`, כך ש-`.github/workflows/publish-catalog.yml` יהיה בשורש ה-Repository.
3. ב-Settings → Pages → Build and deployment → Source בחר `GitHub Actions`.
4. ב-Actions בחר `Build unified Israeli gift-card catalog` והפעל `Run workflow` על הענף `main`.
5. לאחר השלמת הפריסה, בדוק: `https://USERNAME.github.io/couponia-catalog/v3/manifest.json`.
6. שלח את קישור ה-Repository כדי שנגדיר אותו באפליקציה.

**שים לב:** ה-Action הקיים רץ אוטומטית פעם בשבוע, בימי שני (04:23 UTC), ובנוסף ידנית. זהו POC: האיסוף האוטומטי הוא מ-ClawSavings למועמדי הטבות בלבד. ה-JSON המיועד להצגת רשתות מכבדות מבוסס עדיין על קטלוג הפתיחה, ולא על יבוא BUYME חי. אל תציג מידע לא מאומת כמקום מימוש מאושר.
