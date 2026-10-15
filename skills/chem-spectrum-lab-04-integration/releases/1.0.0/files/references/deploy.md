# النشر: Coolify + Docker + VPS

## 1. رفع المشروع على GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <repo-url>
git push -u origin main
```

## 2. في Coolify
- Create New Resource
- Select GitHub Repository
- Build Pack: **Docker Compose**
- حدد `docker/docker-compose.yml`
- Deploy

## 3. بنية Docker (من المهارة 03، تُبنى في أول درس فقط)
- `docker/docker-compose.yml` يربط `frontend` بـ nginx على المنفذ 3000:80
- `docker/Dockerfile.frontend` يبني صورة nginx وينسخ `frontend/`
- `docker/nginx.conf` يخدم SPA مع `try_files` و gzip

## 4. ملاحظات
- التخزين حالياً LocalStorage (لاصقة خادم). عند إضافة backend لاحقاً،
  استبدل داخليات `ChemLabStorage` بنداءات API دون تغيير العقد الظاهر.
- أرقام التواصل واسم المدرس واجبة الظهور في كل صفحة (انظر brand.md).
