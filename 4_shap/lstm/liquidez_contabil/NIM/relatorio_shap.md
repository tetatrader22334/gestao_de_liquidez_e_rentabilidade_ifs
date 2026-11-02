# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_contabil/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_contabil/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
    1                    liquidez_imediata                0.006859                        0.006308            -1.282345e-03
    2 operacoes_de_credito_sobre_captacoes                0.006555                        0.005688            -1.904244e-03
    3          captacoes_sobre_ativo_total                0.003819                        0.002570            -1.315872e-03
    4                          crise_covid                0.003739                        0.003136             3.129976e-03
    5     disponibilidades_sobre_depositos                0.003158                        0.002550             3.946393e-04
    6  depositos_a_prazo_sobre_ativo_total                0.003004                        0.002887             4.445696e-04
    7                              estatal                0.002345                        0.002252            -6.044279e-04
    8               indice_de_imobilizacao                0.002092                        0.001764            -1.589023e-04
    9               ativos_sobre_depositos                0.001876                        0.001680             1.235821e-03
   10  depositos_a_vista_sobre_ativo_total                0.001635                        0.001179             8.863482e-07
   11                            crise_nme                0.001451                        0.000827            -7.596298e-04
   12                 controle_estrangeiro                0.000550                        0.000400            -8.353856e-05
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-11                    0.006180               -0.000461
    2    t                    0.004449               -0.000240
    3 t-10                    0.004020                0.000070
    4  t-9                    0.003103                0.000071
    5  t-1                    0.002777               -0.000232
    6  t-8                    0.002746               -0.000035
    7  t-2                    0.002499               -0.000147
    8  t-7                    0.002405                0.000081
    9  t-4                    0.002287               -0.000004
   10  t-6                    0.002280                0.000118
   11  t-3                    0.002226               -0.000151
   12  t-5                    0.002112                0.000028
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

Tempo total de execução: 76.46 segundos.