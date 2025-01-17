# !/usr/bin/env python
# -*- encoding: utf-8 -*- #
 
# ----------------------------------------------------------------------------------------------------------
# File Name:        Xception_model.py
# Author:           Xianyuer
# Version:          1.0
# Created:          2023/03/22 19:17:08
# Description:      Main Function: Xception model
#                   Cross Reference: NONE
# Function List:    None for outer use
# Input List:
#         <name>       <type>        <description>
#         INPUT        .json         All input parameters
# Output List:
#         <name>       <type>        <description>
#         __NONE__     ---           ---
# History: 
#         <author>     <version>     <time>			<description>
#         Xianyuer     1.0           2023/03/22		XXX
# ----------------------------------------------------------------------------------------------------------

#------------ Load Package ------------#

####### Package: Commonly used #######
import numpy as np
import json

####### Package: Scikit-Learn #######
# import sklearn
# from sklearn.model_selection import train_test_split
# from sklearn.feature_selection import SelectKBest, chi2
# from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder,MinMaxScaler, StandardScaler

####### Package: Pytorch #######
import torch.nn as nn
import torch.nn.functional as F
import torch
from torch import optim
from torch.utils.data import Dataset,DataLoader
from torchinfo import summary


#------------ Load & Set Parameters ------------#

####### Load Input File #######
with open("INPUT.json", 'r', encoding='utf-8') as fw:
    injson = json.load(fw)

####### Load Parameters for Pysical Model #######
maxZnkOrder = injson['Train']['PM']['maxZnkOrder'] # Maximum Order of the Zernike Polynomial
datadim = maxZnkOrder*(maxZnkOrder+3)//2-2


#------------ Model Construction ------------#

class SeparableConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=1, stride=1, padding=0, dilation=1):
        super(SeparableConv, self).__init__()

        self.conv = nn.Conv2d(in_channels, in_channels, kernel_size, stride, padding,
                               dilation, groups=in_channels, bias=False)
        self.pointwise = nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=1, padding=0,
                                   dilation=1, groups=1, bias=False)

    def forward(self, x):
        x = self.conv(x)
        x = self.pointwise(x)
        return x


class Block(nn.Module):
    def __init__(self, in_channels, out_channels, num_conv, strides=1, start_with_relu=True, channel_change=True):
        super(Block, self).__init__()

        if out_channels != in_channels or strides != 1:
            self.shutcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride=strides, bias=False),
                nn.BatchNorm2d(out_channels)
            )
        else:
            self.shutcut = nn.Sequential()

        layers = []
        channels = in_channels

        if channel_change:
            layers.append(nn.ReLU(inplace=True))
            layers.append(SeparableConv(in_channels, out_channels, 3, stride=1, padding=1))
            layers.append(nn.BatchNorm2d(out_channels))
            channels = out_channels

        for i in range(num_conv - 1):
            layers.append(nn.ReLU(inplace=True))
            layers.append(SeparableConv(channels, channels, 3, stride=1, padding=1))
            layers.append(nn.BatchNorm2d(channels))

        if not channel_change:
            layers.append(nn.ReLU(inplace=True))
            layers.append(SeparableConv(in_channels, out_channels, 3, stride=1, padding=1))
            layers.append(nn.BatchNorm2d(out_channels))

        if start_with_relu:
            layers = layers
        else:
            layers = layers[1:]

        if strides != 1:
            layers.append(nn.MaxPool2d(3, strides, 1))

        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        layer = self.layers(x)
        shutcut = self.shutcut(x)
        out = layer + shutcut
        return out


class Xception(nn.Module):
    def __init__(self, num_classes=datadim):

        super(Xception, self).__init__()

        self.num_classes = num_classes

        # Entry flow
        self.entry_flow = nn.Sequential(
            nn.Conv2d(1, 32, 3, 2, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),

            nn.Conv2d(32, 64, 3, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),

            Block(64, 128, 2, 2, start_with_relu=False, channel_change=True),
            Block(128, 256, 2, 2, start_with_relu=True, channel_change=True),
            Block(256, 728, 2, 2, start_with_relu=True, channel_change=True),
        )

        # Middle flow
        self.middle_flow = nn.Sequential(
            Block(728, 728, 3, 1, start_with_relu=True, channel_change=True),
            Block(728, 728, 3, 1, start_with_relu=True, channel_change=True),
            Block(728, 728, 3, 1, start_with_relu=True, channel_change=True),
            Block(728, 728, 3, 1, start_with_relu=True, channel_change=True),
            
        )

        # Exit flow
        self.exit_flow = nn.Sequential(
            Block(728, 1024, 2, 2, start_with_relu=True, channel_change=False),

            SeparableConv(1024, 1536, 3, 1, 1),
            nn.BatchNorm2d(1536),
            nn.ReLU(inplace=True),

            SeparableConv(1536, 2048, 3, 1, 1),
            nn.BatchNorm2d(2048),
            nn.ReLU(inplace=True),

            nn.AdaptiveAvgPool2d((1, 1)),
        )

        self.fc = nn.Linear(2048, num_classes)

    def forward(self, x):
        x = self.entry_flow(x)
        x = self.middle_flow(x)
        x = self.exit_flow(x)
        x = x.view(x.size(0), -1)
        out = self.fc(x)
        return out
    