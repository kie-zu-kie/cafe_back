# cafe_back

Product image uploads are stored in the PostgreSQL `product_images` table so
they persist across Render deploys and restarts. The table is created
automatically from `schema.sql` during application startup.