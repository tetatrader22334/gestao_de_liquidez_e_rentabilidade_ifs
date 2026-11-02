# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_receitas/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_receitas/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
 rank                                                feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                            crise_covid                0.004762                        0.002399                 0.001639
    2 receitas_de_intermediacao_financeira_sobre_ativo_total                0.004544                        0.003052                 0.001042
    3                                      liquidez_imediata                0.004353                        0.004334                -0.001302
    4          rendas_de_operacoes_com_TVM_sobre_ativo_total                0.003742                        0.002525                -0.000086
    5      rendas_de_prestacao_de_servicos_sobre_ativo_total                0.003365                        0.001783                -0.000366
    6          rendas_de_tarifas_bancarias_sobre_ativo_total                0.003243                        0.002301                -0.000348
    7                   operacoes_de_credito_sobre_captacoes                0.003167                        0.002456                -0.000362
    8                            captacoes_sobre_ativo_total                0.003010                        0.002450                -0.001362
    9                                              crise_nme                0.002100                        0.002100                 0.002100
   10                                               nsfr_dec                0.002015                        0.001931                 0.000842
   11                    depositos_a_prazo_sobre_ativo_total                0.001686                        0.001364                -0.001048
   12                    depositos_a_vista_sobre_ativo_total                0.001517                        0.001277                 0.000583
   13                                 indice_de_imobilizacao                0.001203                        0.001049                 0.000294
   14                       disponibilidades_sobre_depositos                0.001199                        0.000909                 0.000650
   15                                                estatal                0.001188                        0.001100                -0.000184
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.015314                0.000565
    2 t-1                    0.012435               -0.000589
    3 t-3                    0.008376                0.000735
    4 t-2                    0.006953                0.000284
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

Tempo total de execução: 89.56 segundos.