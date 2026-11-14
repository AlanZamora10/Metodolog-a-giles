# EduMonitor AI - Frontend React + Vite (Fase B)
# Etapa 1: compilación (TypeScript + Vite)
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# URL pública de Moodle UTA para enlaces externos (p. ej. recuperación de contraseña)
ARG VITE_MOODLE_URL=http://localhost:8080
ENV VITE_MOODLE_URL=$VITE_MOODLE_URL
RUN npm run build

# Etapa 2: Nginx sirve los estáticos y hace de proxy de /api hacia el middleware (sin CORS)
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
