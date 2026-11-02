# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_porte/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_porte/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `4`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 559
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                          crise_covid                0.001959                        0.001653                 0.001272
    2               patrimonio_liquido_log                0.001122                        0.001119                 0.000815
    3                              estatal                0.000816                        0.000748                 0.000089
    4  depositos_a_prazo_sobre_ativo_total                0.000763                        0.000737                -0.000396
    5 operacoes_de_credito_sobre_captacoes                0.000602                        0.000563                 0.000071
    6               indice_de_imobilizacao                0.000554                        0.000536                -0.000012
    7          captacoes_sobre_ativo_total                0.000437                        0.000399                -0.000273
    8  depositos_a_vista_sobre_ativo_total                0.000337                        0.000305                -0.000100
    9                             nsfr_dec                0.000330                        0.000274                 0.000031
   10     disponibilidades_sobre_depositos                0.000328                        0.000310                -0.000200
   11               ativos_sobre_depositos                0.000322                        0.000310                -0.000054
   12                    liquidez_imediata                0.000296                        0.000258                 0.000223
   13                            crise_nme                0.000264                        0.000222                 0.000050
   14                 controle_estrangeiro                0.000262                        0.000239                -0.000060
   15                              lcr_dec                0.000235                        0.000224                -0.000038
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-3                    0.003236                0.000869
    2 t-2                    0.002363                0.000393
    3 t-1                    0.001827                0.000058
    4   t                    0.001380                0.000058
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

Tempo total de execução: 107.39 segundos.