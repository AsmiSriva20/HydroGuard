FROM node:22-slim AS build
WORKDIR /frontend
COPY frontend-react/package*.json ./
RUN npm ci
COPY frontend-react/ ./
ENV VITE_API_BASE=""
RUN npm run build
FROM nginx:alpine
COPY --from=build /frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
