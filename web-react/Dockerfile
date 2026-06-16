FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ARG VITE_LM_STUDIO_TOKEN=""
ENV VITE_LM_STUDIO_TOKEN=$VITE_LM_STUDIO_TOKEN
RUN npm run build

FROM nginx:alpine
# Vite는 build 결과물이 dist 폴더
COPY --from=builder /app/dist /usr/share/nginx/html
# 외부 API 프록시 + SPA 라우팅이 포함된 nginx 설정 적용
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
