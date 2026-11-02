# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_despesas/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_despesas/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
    1 operacoes_de_credito_sobre_captacoes                0.007623                        0.007243                 0.000835
    2  provisao_sobre_operacoes_de_credito                0.004428                        0.004198                 0.000926
    3                    liquidez_imediata                0.003890                        0.003880                -0.000198
    4          despesas_adm_sobre_receitas                0.003835                        0.003759                -0.002919
    5                              estatal                0.002992                        0.002992                -0.000046
    6     disponibilidades_sobre_depositos                0.001725                        0.001575                 0.001021
    7                          crise_covid                0.001178                        0.000766                -0.000564
    8                              lcr_dec                0.001160                        0.001115                -0.000214
    9  depositos_a_prazo_sobre_ativo_total                0.001149                        0.001123                -0.000079
   10  depositos_a_vista_sobre_ativo_total                0.001067                        0.001046                 0.000233
   11                            crise_nme                0.001052                        0.001052                 0.001052
   12          captacoes_sobre_ativo_total                0.001021                        0.000681                 0.000409
   13                             nsfr_dec                0.000887                        0.000741                -0.000194
   14                 controle_estrangeiro                0.000694                        0.000693                 0.000363
   15               ativos_sobre_depositos                0.000616                        0.000461                -0.000247
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-1                    0.006545                0.000278
    2   t                    0.006517                0.000632
    3 t-2                    0.006119                0.000091
    4 t-3                    0.005436               -0.000172
    5 t-4                    0.004869               -0.000293
    6 t-5                    0.004408               -0.000250
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

Tempo total de execução: 69.49 segundos.