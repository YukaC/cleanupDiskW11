---
name: reference-architecture
description: Situation: designing or adopting an architecture decision for a project — choosing an approach, deciding whether a project needs a queue/cache/replicas, writing an ADR, or judging whether an existing project violates the house reference architecture. Not for running the checks (they are already in `check`).
disable-model-invocation: true
---

# Arquitectura de referencia

Los 12 principios están en `docs/contract.md` de `reference-architecture/`. Los verifica
`ra-checks`, que corre dentro de `check`. Esta skill es para lo que **no** se puede
verificar con un script.

## Contrato condensado

BASE (día uno): stateless · config por env, un artefacto · timeout en toda llamada
externa · paginación obligatoria · pool dimensionado · health/readiness · logs
estructurados con correlation id · caché de estáticos · plataforma gestionada antes
que orquestadores · migraciones reversibles · authZ por recurso + validación en el
borde + secretos fuera del repo · tokens de diseño y estados de UI completos ·
artefacto construible.

BAJO MÉTRICA: trabajo pesado fuera del request (p95 > 5 s), cola (deploy interrumpido
por jobs en vuelo), caché de datos (> 20 rps sobre la misma lectura > 20 % del request),
réplicas (pool al 80 % con p95 > 300 ms), microservicios (un release rompe 2 veces/mes),
Kubernetes (nunca por defecto). Umbrales en `docs/under-metric.md`.

## Plantilla ADR

```markdown
# ADR-NNNN — <título>

- Estado: aceptada | propuesta | deprecada
- Fecha: <aaaa-mm-dd>
- Relacionado: SPEC.md §C · §T.n · ADR-mmm

## Contexto
<qué obliga a decidir. Alternativas consideradas. Límites de §C.>

## Decisión
<una o dos líneas accionables, escritas como la regla que seguirán las sesiones.>

## Consecuencias
- Positivas: <qué se gana>
- Costos: <qué se paga: deuda, esquema, complejidad>

## Alternativas
| Alternativa | Por qué se descartó |
|---|---|
| <A> | <motivo, con dato si hay> |
| <B> | <motivo> |
```

## Guardarraíles

`ra-checks <ruta>` corre en modo advertencia. `.ra-check.json` en la raíz del proyecto
activa/desactiva checks y declara rutas de disco permitidas. Pasar a bloqueo cuando
el proyecto esté limpio y el `check` sea obligatorio en CI.

Checks que no aplican se saltan y se informan; nunca fallan por ausencia. Lo que no
tiene verificación automática posible (authZ por recurso, límites de error, cuándo partir
un monolito) se decide con ADR y métrica, no con un check.