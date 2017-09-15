[![CircleCI](https://circleci.com/gh/cloudify-incubator/cloudify-kubernetes-plugin.svg?style=svg)](https://circleci.com/gh/cloudify-incubator/cloudify-kubernetes-plugin)

# Cloudify Kubernetes Plugin

### Overview

Cloudify Kubernetes Plugin enables possibility of creating and deleting resources
hosted by some Kubernetes cluster using Cloudify blueprints.

Plugin is using Kubernetes python client
(https://github.com/kubernetes-incubator/client-python)
to communicate with Kubernetes Master API.

All node types and relationships exposed by plugin are defined in *plugin.yaml* file.

Main entrypoints to python logic are defined in *tasks.py* file.


#### Blueprint concept

Plugin exposes two kinds of node types:

* ***cloudify.kubernetes.nodes.Master***
    
    Node type describes Kubernetes maser configuration.
    It is responsible for handling all data required to use Kubernetes API from outside.
    Every blueprint using plugin has to define node template of this type.
    It defines two properties:

    - ***configuration***
    
    - ***authentication***
     
* ***cloudify.kubernetes.resources.****

    Family of node types designed to describe Kubernetes resources (e.g. Pods, Deployments, Services etc.)
    Plugin supports different ways of Kubernetes resources definition.
    Resources definition used in Cloudify blueprints are also compliant with Kubernetes YAML schema. 

Plugin defines also one relationship:

***cloudify.kubernetes.relationships.managed_by_master***

It is required for each ***cloudify.kubernetes.resources.**** node template
to be bounded using this relationship to the ***cloudify.kubernetes.nodes.Master*** node template.

During installation of deployment for all *cloudify.kubernetes.resources.** nodes 
plugin is looking for target of defined *managed_by_master* relationship to find related Master node.
Data stored by Master node bounded using relationship to Resource node will be used to perform API call to create / delete this resource.
Result of each operation is stored in *kubernetes* runtime_property for each resource node.

```
  master:
    type: cloudify.kubernetes.nodes.Master
    properties:
      configuration:
        file_content: { get_input: kubernetes_configuration_file_content }

  resource:
    type: cloudify.kubernetes.resources.Pod
    properties:
      [...]
      - type: cloudify.kubernetes.relationships.managed_by_master
        target: master
           
```

### Master configuration possibilities

There are four possible ways of *cloudify.kubernetes.nodes.Master* (Kubernetes API python client) configuration.
Each method is associated with one key (below) and required value which you should put under *configuration* property of *cloudify.kubernetes.nodes.Master* node.
For each Master node you should choose one method (one dictionary entry for *configuration* property should be defined): 

 * ***blueprint_file_name*** - value should be relative to the blueprint path to Kubernetes config file (contained by blueprint archive)
 
 * ***manager_file_path*** - value should be absolute path to Kubernetes config file previously uploaded into Cloudify Manager virtual machine
 
 * ***file_content*** - value should be (YAML) content of Kubernetes config file 
 
 * ***api_options*** - value should be a dictionary contains basic Kubernetes API properties:
    - *host* (HTTP/HTTPS URL to Kubernetes API)
    - *ssl_ca_cert*
    - *cert_file*
    - *key_file*
    - *verify_ssl*

Kubernetes config file is by default stored in:

```~/.kube/config```

on Kubernetes Master VM. You can also obtain it executing:

```kubectl config view --raw```

### Master authentication possibilities

Plugin has been designed to support different Kubernetes clusters providers.
For now only Google Cloud Platform is supported.
As *authentication* property of Master node you can specify dictionary with key and value: 

 * ***gcp_service_account*** -  value should be (JSON) content of Google Cloud Platform Service Accout file

### Resources definition possibilities

 * ***cloudify.kubernetes.resources.BlueprintDefinedResource***
    
    Simplest way to define kubernetes resource.
    It uses Kubernetes YAML description to define resource.
    Properties of *cloudify.kubernetes.resources.BlueprintDefinedResource*:
        
    - *definition* - Kubernetes YAML resource definition
    - *options* - Kubernetes python client operation options

    Only subtypes of BlueprintDefinedResource can be used.
    Each subtype represents single kind of kubernetes resource.
    Currently supported resources:

    - *cloudify.kubernetes.resources.Deployment*
    - *cloudify.kubernetes.resources.Pod*
    - *cloudify.kubernetes.resources.ReplicaSet*
    - *cloudify.kubernetes.resources.ReplicationController*
    - *cloudify.kubernetes.resources.Service*
    - *cloudify.kubernetes.resources.PersistentVolume*
    - *cloudify.kubernetes.resources.StorageClass*
    
    Example blueprint:
  
    ```examples/simple-blueprint_defined_resource.yaml```
 
 * ***cloudify.kubernetes.resources.CustomBlueprintDefinedResource***
 
    Node type extending *cloudify.kubernetes.resources.BlueprintDefinedResource*.
    It has been introduced to support some custom kinds of Kubernetes resources
    which hasn't defined their own subtype definition in *plugin.yaml*.
    
    This node type has the same properties like *BlueprintDefinedResource* 
    and additional one: *api_mapping* - containing information about Kubernetes python client objects
    which should be used to create / delete this resource object on Kubernetes cluster.
    
    ```
        create:
          api: CoreV1Api
          method: create_namespaced_pod
          payload: V1Pod
        read:
          api: CoreV1Api
          method: read_namespaced_pod
        delete:
          api: CoreV1Api
          method: delete_namespaced_pod
          payload: V1DeleteOptions
    ```
    Detailed info about Kubernetes python client objects / methods you can find here:
    
    https://github.com/kubernetes-incubator/client-python/tree/master/kubernetes
 
    Example blueprint:
  
    ```examples/simple-custom_blueprint_defined_resource.yaml```
 
 * ***cloudify.kubernetes.resources.FileDefinedResource***
 
    It enables creation / deletion of Kubernetes resource defined in YAML file.
    This file may be specified using relative path to file in blueprint or external URL.
    It should be defined as *file/resource_path* property.

    Example blueprint:
  
    ```examples/simple-file_defined_resource.yaml``` 
 
 * ***cloudify.kubernetes.resources.MultipleFileDefinedResources***

    The same like *cloudify.kubernetes.resources.FileDefinedResource*, but it takes list of multiple kubernetes resources to be deployed.
    This list should be defined as *files* property. Each item in this list should be one-item dictionary contains *resource_path* key and path / URL to file as value.

    Example blueprint:
  
    ```examples/simple-multiple_file_defined_resources.yaml```