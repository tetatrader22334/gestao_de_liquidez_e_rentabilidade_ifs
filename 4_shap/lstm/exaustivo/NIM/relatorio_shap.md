# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/exaustivo/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/exaustivo/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
 rank                                                   feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                             pib_indice_sa                0.002866                        0.001506                 0.000233
    2                                         pib_indice_sa_log                0.002724                        0.001594                -0.000444
    3         rendas_de_prestacao_de_servicos_sobre_ativo_total                0.002033                        0.000896                 0.000089
    4 resultado_de_provisao_para_creditos_de_dificil_liquidacao                0.001814                        0.001079                -0.000588
    5                                    ativos_sobre_captacoes                0.001589                        0.001530                -0.000505
    6    receitas_de_intermediacao_financeira_sobre_ativo_total                0.001575                        0.001067                -0.000019
    7                       provisao_sobre_operacoes_de_credito                0.001536                        0.000909                -0.000469
    8                      despesas_de_intermediacao_financeira                0.001447                        0.001297                -0.000821
    9             rendas_de_operacoes_com_TVM_sobre_ativo_total                0.001437                        0.001109                -0.000426
   10                                         liquidez_imediata                0.001391                        0.001213                -0.000301
   11          rendas_de_operacoes_de_credito_sobre_ativo_total                0.001363                        0.000682                 0.000015
   12                            rendas_de_operacoes_de_credito                0.001355                        0.000832                -0.000360
   13                  despesas_de_intermediacao_sobre_receitas                0.001208                        0.000937                -0.000676
   14             resultado_de_provisao_pcddl_sobre_ativo_total                0.001183                        0.000552                -0.000168
   15   resultado_de_intermediacao_financeira_sobre_ativo_total                0.001161                        0.000983                -0.000374
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.032226               -0.003724
    2 t-1                    0.009081               -0.000809
    3 t-2                    0.004923               -0.000741
    4 t-3                    0.003921               -0.000568
    5 t-4                    0.003306               -0.000416
    6 t-5                    0.002838               -0.000310
    7 t-6                    0.002570               -0.000283
    8 t-7                    0.002181               -0.000191
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

Tempo total de execução: 326.15 segundos.