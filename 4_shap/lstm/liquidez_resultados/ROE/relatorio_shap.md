# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_resultados/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_resultados/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `8`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 503
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                 feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1           resultado_de_provisao_pcddl_sobre_ativo_total                0.016587                        0.010248                -0.000635
    2 resultado_de_intermediacao_financeira_sobre_ativo_total                0.012953                        0.009124                 0.001022
    3                    operacoes_de_credito_sobre_captacoes                0.007581                        0.002449                -0.000111
    4                                  indice_de_imobilizacao                0.007189                        0.004705                 0.001162
    5                     depositos_a_vista_sobre_ativo_total                0.006472                        0.002492                 0.000438
    6                                       liquidez_imediata                0.005520                        0.003705                 0.002520
    7                             captacoes_sobre_ativo_total                0.004256                        0.003313                -0.001796
    8                                                 estatal                0.004194                        0.004066                -0.000031
    9                                                nsfr_dec                0.002934                        0.001039                -0.000438
   10                                                 lcr_dec                0.002469                        0.001563                 0.000530
   11                                               crise_nme                0.002366                        0.002090                 0.002090
   12                        disponibilidades_sobre_depositos                0.002350                        0.001334                -0.000829
   13                     depositos_a_prazo_sobre_ativo_total                0.002331                        0.001199                -0.000519
   14                                             crise_covid                0.001894                        0.001218                 0.001218
   15                                    controle_estrangeiro                0.001648                        0.001646                 0.000630
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.018564               -0.001885
    2   t                    0.015955                0.001192
    3 t-1                    0.009698                0.000148
    4 t-5                    0.008634                0.000664
    5 t-3                    0.008103                0.000248
    6 t-2                    0.007707                0.000761
    7 t-6                    0.007586                0.001651
    8 t-4                    0.006110                0.001490
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

Tempo total de execução: 246.09 segundos.