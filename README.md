# Dashboard Académico Híbrido (PWA / Local Server)

Sistema de gestión analítica y automatización de recordatorios desarrollado para optimizar la carga operativa del cuarto semestre de Ciencia de Datos para Negocios.

## Arquitectura Dual

El proyecto está diseñado para operar en dos entornos:

- Modo Web Privado (Serverless): Despliegue estático que utiliza localStorage para garantizar la privacidad de los datos de cada usuario.
- Modo Servidor Local (Full Stack): Backend orquestado en Python con base de datos SQLite para persistencia estructurada.

## Características Técnicas Principales

- Automatización de Notificaciones: Hilo en segundo plano que procesa cronogramas y dispara alertas vía SMTP para entregas críticas.
- Calculadora Analítica de Riesgo: Motor lógico que procesa el peso de criterios de evaluación y proyecta el rendimiento mínimo viable para aprobar la materia.
- Testing Automatizado: Scripts de validación de endpoints y conteo de registros para asegurar la integridad de la base de datos y la red.

## Stack Tecnológico

- Frontend: HTML5, CSS3, JavaScript.
- Backend: Python (http.server), SQLite.
- Despliegue: Netlify / Batch Scripts para entorno local en Windows.
