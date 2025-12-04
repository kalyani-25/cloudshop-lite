# Stage 1: Build the frontend (React/Vite)
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Run with Nginx
FROM nginx:1.27-alpine

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from Vite build
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
