FROM nginx:stable-alpine

# Clean default nginx content
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build from frontend
COPY frontend/dist /usr/share/nginx/html/

# Copy nginx config
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

