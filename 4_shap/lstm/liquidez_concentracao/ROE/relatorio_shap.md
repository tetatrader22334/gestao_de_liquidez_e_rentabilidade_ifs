# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `6`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 531
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                      hhi_periodo_dec                0.006762                        0.006760                 0.006760
    2                              estatal                0.006183                        0.006183                 0.000049
    3 operacoes_de_credito_sobre_captacoes                0.002262                        0.002170                -0.000116
    4                          crise_covid                0.001964                        0.001340                 0.000587
    5  depositos_a_vista_sobre_ativo_total                0.001931                        0.001903                -0.000100
    6  depositos_a_prazo_sobre_ativo_total                0.001909                        0.001832                -0.000539
    7               indice_de_imobilizacao                0.001737                        0.001678                -0.000047
    8                            crise_nme                0.001609                        0.001563                 0.001563
    9                    liquidez_imediata                0.001472                        0.001268                 0.000748
   10          captacoes_sobre_ativo_total                0.001408                        0.001396                -0.000265
   11                             nsfr_dec                0.001231                        0.001084                -0.000455
   12                     market_share_dec                0.001180                        0.001128                 0.000455
   13               ativos_sobre_depositos                0.000906                        0.000871                -0.000699
   14                              lcr_dec                0.000881                        0.000804                 0.000236
   15     disponibilidades_sobre_depositos                0.000856                        0.000819                -0.000109
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.007986                0.001208
    2 t-1                    0.006352                0.001508
    3 t-2                    0.005533                0.001523
    4 t-3                    0.004855                0.001546
    5 t-4                    0.004326                0.001340
    6 t-5                    0.003880                0.001231
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

Tempo total de execução: 71.99 segundos.