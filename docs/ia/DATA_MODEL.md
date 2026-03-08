# Data Model

Base de datos: SQLite

Tablas principales:

## user

usuario único del sistema

campos:

id
username
password_hash
recovery_question
recovery_answer_hash
created_at

## accounts

cuentas financieras

tipos:

bank
virtual_wallet
cash

## categories

categorías de ingresos y gastos

type:

income
expense

## transactions

movimientos financieros

type:

income
expense

## transfers

transferencias entre cuentas

## budgets

presupuestos mensuales

## investments

operaciones de inversión

buy
sell

## precios_mercado

cache de precios de activos

## cotizaciones_cache

cotizaciones de monedas y cripto

## config

configuración del sistema
