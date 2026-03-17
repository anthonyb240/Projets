FROM nginx:alpine

# Supprimer la config par défaut
RUN rm -rf /usr/share/nginx/html/*

# Copier les fichiers front (templates + static)
COPY templates/ /usr/share/nginx/html/
COPY static/ /usr/share/nginx/html/static/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
