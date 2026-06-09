FROM node:22-slim
WORKDIR /app
COPY apps/web/package.json ./
RUN npm install --no-audit --no-fund
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
