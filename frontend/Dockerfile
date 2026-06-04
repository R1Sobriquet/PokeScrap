FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Serveur de développement Vite (Jalon 1). Le build de prod viendra plus tard.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
