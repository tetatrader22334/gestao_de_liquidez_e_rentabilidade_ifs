# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_porte/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_porte/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `12`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 447
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                          crise_covid                0.007660                        0.004679                 0.004328
    2                              estatal                0.005592                        0.005554                -0.000555
    3               patrimonio_liquido_log                0.004295                        0.004277                 0.002253
    4  depositos_a_vista_sobre_ativo_total                0.003073                        0.002951                 0.000066
    5               indice_de_imobilizacao                0.002760                        0.002572                 0.000362
    6                 controle_estrangeiro                0.002644                        0.002643                 0.001141
    7                    liquidez_imediata                0.002066                        0.001465                -0.000696
    8  depositos_a_prazo_sobre_ativo_total                0.001870                        0.001230                -0.000628
    9 operacoes_de_credito_sobre_captacoes                0.001571                        0.001483                -0.000297
   10          captacoes_sobre_ativo_total                0.001560                        0.001041                 0.000368
   11                            crise_nme                0.001362                        0.001266                 0.001138
   12                             nsfr_dec                0.001345                        0.000823                -0.000264
   13                              lcr_dec                0.001046                        0.000884                -0.000311
   14     disponibilidades_sobre_depositos                0.001014                        0.000595                -0.000146
   15               ativos_sobre_depositos                0.000705                        0.000565                -0.000346
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1    t                    0.005156               -0.000417
    2  t-1                    0.003834                0.000032
    3  t-2                    0.003670                0.000418
    4  t-3                    0.003403                0.000537
    5  t-4                    0.003151                0.000652
    6  t-5                    0.003104                0.000770
    7  t-6                    0.002912                0.000855
    8  t-7                    0.002860                0.000840
    9  t-8                    0.002824                0.000763
   10  t-9                    0.002774                0.000715
   11 t-10                    0.002656                0.000568
   12 t-11                    0.002640                0.000523
```

## Arquivos gerados
- `shap_values_flat.npy`
- `shap_values_3d.npy`
- `shap_base_values.npy`
- `metadados_amostras_shap.csv`
- `shap_importance_lag_feature.csv`
- `shap_importance_feature_aggregated.csv`
- `shap_importance_by_lag.csv`
- `shap_bar_flat_top.png`
- `shap_beeswarm_flat_top.png`
- `shap_bar_feature_aggregated_top.png`
- `shap_heatmap_feature_lag_top.png`

Tempo total de execução: 109.12 segundos.