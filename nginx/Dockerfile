FROM nginx:1.27-alpine

# Remove default static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built frontend (make sure frontend/dist exists)
COPY frontend/dist /usr/share/nginx/html/

# Use our custom nginx config (with /users, /catalog, /orders, /aiops)
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
