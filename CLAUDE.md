# MCP GOOGLE ADS

Cosas que debes cumplir:

- Siempre que mencione el hotel 1272, debes tener en cuenta que se trata del hotel Migjorn Ibiza Suites & Spa.

- Cuando te solicite información sobre Google ADS, siempre debes hacerlo a través del MCP de Google ADS, llamado: googleAdsServer

- La cuenta que vamos a utilizar siempre de referencia en Google ADS, es del Hotel Mijgorn Ibiza Suites & SPA, con ID: 9759913507, que está dentro de la cuenta maestra MCC con ID: 1005152089

- El Account 9759913507 uses currency: "EUR"


# NT2D
- Cuando te solicite información de las reservas de neobookings, debes hacerlo a través del MCP NT2D y tener en cuenta el archivo D:\devprojects\nostromo\docs\database-engineering\2.analisis-relaciones-db-neo.md para entender la base de datos

La consulta clásica para obtener reservas es esta, tenla en cuenta para no probar cosas nuevas:

● NT2D - execute_sql (MCP)(sql: "SELECT \n  r.identificador as reserva_id,\n  r.estado,\n  rh.fecha_entrada,\n  rh.fecha_salida,\n  DATEDIFF(rh.fecha_salida, rh.fecha_entrada) as noches,\n  r.nombre,\n  r.apellidos,\n    
                          r.email,\n  r.telefono,\n  r.pais,\n  r.moneda,\n  r.precio_total,\n  r.metodo_pago,\n  rh.adultos,\n  rh.ninos,\n  rh.bebes,\n  CONCAT(rh.adultos + rh.ninos + rh.bebes) as total_pax,\n
                          rh.cantidad as num_habitaciones\nFROM nb_reservas r\nINNER JOIN nb_reservas_habitaciones rh ON r.identificador = rh.identificador\nWHERE rh.id_hotel_rh = 1272 \n  AND rh.fecha_entrada BETWEEN    
                          '2025-06-01' AND '2025-06-30'\nORDER BY rh.fecha_entrada ASC;")

LA consulta para obtener los códigos promo es esta:

NT2D - execute_sql (MCP)(sql: "SELECT \n  o.id_oferta,\n  o.codigo_promo,\n  o.descuento,\n  o.tipo,\n  o.fecha_aplicacion_ini,\n  o.fecha_aplicacion_fin,\n  o.activa,\n  o.aplicacion\nFROM nb_ofertas o\nWHERE o.id_hotel = 1272 \n  AND 
                          o.codigo_promo IS NOT NULL\n  AND o.codigo_promo != ''\nORDER BY o.fecha_aplicacion_fin DESC\nLIMIT 20")